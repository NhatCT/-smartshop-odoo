"""
MCP Cache — In-memory TTL Cache cho Odoo MCP tool results.
TTL mặc định: 30 phút (configurable).
Chiến lược: Cache READ operations (search_records, read_record, aggregate_records).
            KHÔNG cache WRITE operations (execute_method, execute_write).
"""

import time
import hashlib
import threading
from collections import OrderedDict
from typing import Any


# Tools cần cache (READ-only)
CACHEABLE_TOOLS = {"search_records", "read_record", "aggregate_records", "get_fields"}
# Tools không cache (WRITE operations)
NON_CACHEABLE_TOOLS = {"execute_method", "execute_write", "create_record", "update_record", "delete_record"}


class MCPCache:
    """
    In-memory TTL Cache cho MCP tool results.
    Thread-safe, LRU eviction khi đầy bộ nhớ.
    """

    def __init__(self, ttl_seconds: int = 1800, max_entries: int = 5000):
        """
        Args:
            ttl_seconds: Thời gian sống của cache (mặc định 30 phút = 1800s)
            max_entries: Số lượng entries tối đa trước khi evict LRU
        """
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "invalidations": 0}

    def _make_key(self, tool_name: str, tool_input: dict) -> str:
        """Tạo cache key từ tool_name + input hash."""
        raw = f"{tool_name}:{sorted(tool_input.items())}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def should_cache(self, tool_name: str) -> bool:
        """Kiểm tra tool có nên cache không."""
        return tool_name in CACHEABLE_TOOLS

    def get(self, tool_name: str, tool_input: dict) -> tuple[bool, Any]:
        """
        Tìm cached result.
        Returns: (cache_hit: bool, result: Any | None)
        """
        if not self.should_cache(tool_name):
            return False, None

        key = self._make_key(tool_name, tool_input)
        now = time.time()

        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return False, None

            entry = self._cache[key]
            if now - entry["timestamp"] > self._ttl:
                del self._cache[key]
                self._stats["misses"] += 1
                return False, None

            # LRU: move to end
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return True, entry["result"]

    def set(self, tool_name: str, tool_input: dict, result: Any) -> None:
        """Lưu result vào cache."""
        if not self.should_cache(tool_name):
            return

        key = self._make_key(tool_name, tool_input)

        with self._lock:
            if len(self._cache) >= self._max_entries:
                # LRU eviction
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1

            self._cache[key] = {
                "result": result,
                "timestamp": time.time(),
                "tool_name": tool_name
            }
            self._cache.move_to_end(key)

    def invalidate_by_tool(self, tool_name: str) -> int:
        """Xóa tất cả cache entries của một tool cụ thể."""
        with self._lock:
            keys_to_delete = [
                k for k, v in self._cache.items()
                if v.get("tool_name") == tool_name
            ]
            for key in keys_to_delete:
                del self._cache[key]
            self._stats["invalidations"] += len(keys_to_delete)
            return len(keys_to_delete)

    def clear(self) -> None:
        """Xóa toàn bộ cache."""
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> dict:
        """Lấy thống kê cache performance."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0
            return {
                **self._stats,
                "total_requests": total,
                "hit_rate_pct": round(hit_rate * 100, 1),
                "current_entries": len(self._cache),
                "ttl_seconds": self._ttl,
                "max_entries": self._max_entries
            }

    def cleanup_expired(self) -> int:
        """Dọn dẹp expired entries — gọi định kỳ."""
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._cache.items() if now - v["timestamp"] > self._ttl]
            for key in expired:
                del self._cache[key]
            return len(expired)


# Singleton cache instance
_mcp_cache = MCPCache(ttl_seconds=1800, max_entries=5000)


def get_mcp_cache() -> MCPCache:
    return _mcp_cache
