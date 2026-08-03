"""
LangFuse Tracker — Tầng 6: Observability
Cost tracking, latency monitoring, và trace logging qua LangFuse Cloud.

FREE TIER: 50,000 traces/tháng — đủ cho SmartShop.
Setup: Đăng ký tại cloud.langfuse.com → lấy LANGFUSE_SECRET_KEY + LANGFUSE_PUBLIC_KEY.

Nếu LangFuse chưa được cấu hình → tự động fallback sang console logging (no-op mode).
"""

from __future__ import annotations
import os
import time
import uuid
from typing import Any

# Lazy import LangFuse — nếu chưa install hoặc chưa config thì dùng no-op
_langfuse_available = False
_langfuse_client = None


def _init_langfuse():
    global _langfuse_available, _langfuse_client
    secret = os.getenv("LANGFUSE_SECRET_KEY", "")
    public = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not secret or not public:
        print("   ℹ️ [LANGFUSE] Chưa cấu hình key — dùng console logging mode.")
        return

    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            secret_key=secret,
            public_key=public,
            host=host,
            debug=False
        )
        _langfuse_available = True
        print(f"   ✅ [LANGFUSE] Connected to {host}")
    except ImportError:
        print("   ⚠️ [LANGFUSE] Package chưa được cài. Chạy: pip install langfuse")
    except Exception as e:
        print(f"   ⚠️ [LANGFUSE] Không thể kết nối: {e}")


class TraceContext:
    """Context object cho một request trace."""

    def __init__(self, trace_id: str, trace=None):
        self.trace_id = trace_id
        self._trace = trace  # LangFuse trace object hoặc None
        self._spans: list = []
        self.start_time = time.time()

    def span(self, name: str, input_data: Any = None) -> "SpanContext":
        return SpanContext(self, name, input_data)

    def finish(self, output: str = "", level: str = "DEFAULT") -> None:
        if self._trace:
            try:
                self._trace.update(output=output[:2000], level=level)
            except Exception:
                pass


class SpanContext:
    """Context object cho một agent span trong trace."""

    def __init__(self, trace_ctx: TraceContext, name: str, input_data: Any = None):
        self._trace_ctx = trace_ctx
        self._name = name
        self._span = None
        self._start = time.time()

        if trace_ctx._trace:
            try:
                self._span = trace_ctx._trace.span(
                    name=name,
                    input=str(input_data)[:500] if input_data else None
                )
            except Exception:
                pass

    def finish(self, output: Any = None, metadata: dict | None = None) -> float:
        elapsed_ms = (time.time() - self._start) * 1000
        if self._span:
            try:
                self._span.end(
                    output=str(output)[:1000] if output else None,
                    metadata=metadata
                )
            except Exception:
                pass
        return elapsed_ms


class LangFuseTracker:
    """
    LangFuse Cost & Latency Tracker cho SmartShop AI Gateway.
    Tự động fallback sang console logging nếu LangFuse chưa setup.
    """

    def __init__(self):
        if not _langfuse_available:
            _init_langfuse()
        self._session_id = str(uuid.uuid4())[:8]
        self._daily_cost_usd = 0.0
        self._daily_requests = 0

    def start_trace(
        self,
        user_id: str,
        channel: str,
        input_text: str,
        user_role: str = "viewer"
    ) -> TraceContext:
        """Bắt đầu một trace mới cho một request."""
        trace_id = str(uuid.uuid4())[:12]

        trace_obj = None
        if _langfuse_available and _langfuse_client:
            try:
                trace_obj = _langfuse_client.trace(
                    id=trace_id,
                    name=f"smartshop-{channel}",
                    user_id=str(user_id),
                    input=input_text[:500],
                    session_id=self._session_id,
                    tags=[channel, user_role, "smartshop"],
                    metadata={
                        "channel": channel,
                        "user_role": user_role,
                        "session": self._session_id
                    }
                )
            except Exception as e:
                print(f"   ⚠️ [LANGFUSE TRACE START] {e}")

        return TraceContext(trace_id, trace_obj)

    def log_generation(
        self,
        trace_ctx: TraceContext,
        model: str,
        input_tokens: int,
        output_tokens: int,
        agent_name: str = ""
    ) -> dict:
        """
        Ghi nhận token usage và cost estimate.
        Claude Haiku pricing: ~$0.80/M input tokens, $4.00/M output tokens.
        """
        # Claude Haiku cost estimation (USD)
        input_cost = input_tokens * 0.80 / 1_000_000
        output_cost = output_tokens * 4.00 / 1_000_000
        total_cost_usd = input_cost + output_cost
        total_cost_vnd = total_cost_usd * 25000  # ~25,000 VNĐ/USD

        self._daily_cost_usd += total_cost_usd
        self._daily_requests += 1

        if _langfuse_available and _langfuse_client and trace_ctx._trace:
            try:
                trace_ctx._trace.generation(
                    name=f"{agent_name}-generation",
                    model=model,
                    usage={
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": input_tokens + output_tokens,
                        "unit": "TOKENS"
                    },
                    metadata={
                        "cost_usd": round(total_cost_usd, 6),
                        "cost_vnd": round(total_cost_vnd, 1),
                        "agent": agent_name
                    }
                )
            except Exception as e:
                print(f"   ⚠️ [LANGFUSE GENERATION] {e}")
        else:
            print(
                f"   📊 [COST] {agent_name} | "
                f"In={input_tokens} Out={output_tokens} | "
                f"~{total_cost_vnd:.0f} VNĐ"
            )

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": total_cost_usd,
            "cost_vnd": total_cost_vnd
        }

    def flush(self) -> None:
        """Flush pending traces tới LangFuse cloud."""
        if _langfuse_available and _langfuse_client:
            try:
                _langfuse_client.flush()
            except Exception:
                pass

    def get_session_stats(self) -> dict:
        return {
            "session_id": self._session_id,
            "total_requests": self._daily_requests,
            "total_cost_usd": round(self._daily_cost_usd, 6),
            "total_cost_vnd": round(self._daily_cost_usd * 25000, 0),
            "langfuse_active": _langfuse_available
        }


# Singleton tracker
_tracker: LangFuseTracker | None = None


def get_tracker() -> LangFuseTracker:
    global _tracker
    if _tracker is None:
        _tracker = LangFuseTracker()
    return _tracker
