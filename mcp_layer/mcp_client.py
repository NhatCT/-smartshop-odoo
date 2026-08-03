"""
MCP Client Wrapper — Tầng 5: Odoo MCP Layer
Wrapper quanh MCP ClientSession với:
- 30min TTL Cache (READ-only tools)
- Fallback: phục vụ stale cache nếu Odoo down
- Async timeout: 15 giây mỗi tool call
- Retry logic: 2 lần retry khi timeout
"""

from __future__ import annotations
import asyncio
import time
from typing import Any
from mcp import ClientSession

from .mcp_cache import MCPCache, get_mcp_cache

TOOL_TIMEOUT_SECONDS = 15.0
MAX_RETRIES = 2


class MCPToolResult:
    """Wrapper quanh MCP tool result chuẩn hóa."""
    def __init__(self, content: str, cached: bool = False, from_fallback: bool = False):
        self.content = [type("C", (), {"text": content})()]
        self.cached = cached
        self.from_fallback = from_fallback
        self.timestamp = time.time()


class MCPClientWrapper:
    """
    Proxy cho MCP ClientSession với Cache + Fallback + Timeout.
    Thay thế trực tiếp `session.call_tool()` trong Agent code.
    """

    def __init__(self, session: ClientSession, cache: MCPCache | None = None):
        self._session = session
        self._cache = cache or get_mcp_cache()
        self._fallback_store: dict[str, dict] = {}  # Stale data fallback
        self._stats = {"cache_hits": 0, "cache_misses": 0, "timeouts": 0, "fallbacks": 0, "errors": 0}

    async def call_tool(self, tool_name: str, tool_input: dict | None = None) -> MCPToolResult:
        """
        Gọi MCP tool với Cache + Fallback + Timeout.
        Interface giống hệt `session.call_tool()` để drop-in replacement.
        """
        tool_input = tool_input or {}

        # 1. Cache check (READ tools only)
        hit, cached_result = self._cache.get(tool_name, tool_input)
        if hit:
            self._stats["cache_hits"] += 1
            print(f"   ⚡ [MCP CACHE HIT] {tool_name}")
            return MCPToolResult(cached_result, cached=True)

        self._stats["cache_misses"] += 1

        # 2. Gọi Odoo MCP với timeout + retry
        result_text = None
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                raw_result = await asyncio.wait_for(
                    self._session.call_tool(tool_name, tool_input),
                    timeout=TOOL_TIMEOUT_SECONDS
                )
                result_text = raw_result.content[0].text if raw_result.content else "OK"
                break  # Success

            except asyncio.TimeoutError:
                self._stats["timeouts"] += 1
                last_error = f"Timeout sau {TOOL_TIMEOUT_SECONDS}s"
                print(f"   ⚠️ [MCP TIMEOUT] {tool_name} attempt {attempt+1}/{MAX_RETRIES+1}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Backoff

            except Exception as e:
                last_error = str(e)
                self._stats["errors"] += 1
                print(f"   ❌ [MCP ERROR] {tool_name}: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(0.5 * (attempt + 1))

        if result_text is not None:
            # 3. Store in cache (READ tools)
            self._cache.set(tool_name, tool_input, result_text)
            # Store as fallback data
            cache_key = f"{tool_name}:{sorted(tool_input.items())}"
            self._fallback_store[cache_key] = {"text": result_text, "timestamp": time.time()}
            return MCPToolResult(result_text, cached=False)

        # 4. Fallback: dùng stale cache nếu Odoo down
        cache_key = f"{tool_name}:{sorted(tool_input.items())}"
        if cache_key in self._fallback_store:
            self._stats["fallbacks"] += 1
            stale = self._fallback_store[cache_key]
            age_min = (time.time() - stale["timestamp"]) / 60
            print(f"   🔄 [MCP FALLBACK] {tool_name} — dữ liệu cũ {age_min:.0f}m")
            return MCPToolResult(
                stale["text"] + f"\n_(⚠️ Dữ liệu có thể lỗi thời {age_min:.0f} phút — Odoo đang không khả dụng)_",
                from_fallback=True
            )

        # 5. Hard fail
        raise RuntimeError(f"MCP tool '{tool_name}' thất bại sau {MAX_RETRIES+1} lần: {last_error}")

    async def call_write_tool(self, tool_name: str, tool_input: dict | None = None) -> MCPToolResult:
        """
        Gọi WRITE tool — KHÔNG cache, không fallback, timeout ngắn hơn.
        Dùng cho execute_method, execute_write, create_record.
        """
        tool_input = tool_input or {}
        try:
            raw_result = await asyncio.wait_for(
                self._session.call_tool(tool_name, tool_input),
                timeout=TOOL_TIMEOUT_SECONDS
            )
            result_text = raw_result.content[0].text if raw_result.content else "OK"
            # Invalidate related cache sau WRITE
            self._cache.invalidate_by_tool("search_records")
            self._cache.invalidate_by_tool("read_record")
            return MCPToolResult(result_text)
        except asyncio.TimeoutError:
            raise RuntimeError(f"WRITE tool '{tool_name}' timeout sau {TOOL_TIMEOUT_SECONDS}s")
        except Exception as e:
            raise RuntimeError(f"WRITE tool '{tool_name}' error: {e}")

    def get_stats(self) -> dict:
        """Lấy performance stats của MCP layer."""
        cache_stats = self._cache.get_stats()
        return {
            "mcp_layer": self._stats,
            "cache": cache_stats
        }
