"""
SmartShop AI Gateway — Langfuse Tracing Setup
==============================================
Implements tracing theo Langfuse Skill best practices:

1. AnthropicInstrumentor (OTel) — tự động capture model, tokens, cost
2. @observe decorator — trace từng agent với tên ổn định
3. session_id — gom messages cùng conversation
4. user_id — track cost per user
5. Tags: channel, role — filter theo business dimension
6. PII masking — email bị mask trong traces
7. flush() on shutdown — đảm bảo traces được gửi

Import thứ tự QUAN TRỌNG:
  1. load_dotenv() trước
  2. setup_langfuse_tracing() trước khi import anthropic
"""

from __future__ import annotations
import os
import re
from typing import Any

# === Khởi tạo Langfuse TRƯỚC KHI import anthropic (bắt buộc per skill) ===
_langfuse_initialized = False
_langfuse_client = None


def setup_langfuse_tracing() -> bool:
    """
    Khởi tạo Langfuse tracing với AnthropicInstrumentor.
    Phải được gọi TRƯỚC KHI import anthropic client.
    Returns True nếu setup thành công.
    """
    global _langfuse_initialized, _langfuse_client

    if _langfuse_initialized:
        return True

    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not secret_key or not public_key:
        print("   ℹ️ [LANGFUSE] Keys chưa cấu hình — tracing disabled. Thêm LANGFUSE_SECRET_KEY + LANGFUSE_PUBLIC_KEY vào .env")
        return False

    try:
        # Bước 1: Khởi tạo Langfuse SDK
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            secret_key=secret_key,
            public_key=public_key,
            host=host,
        )

        # Bước 2: Instrument Anthropic SDK (OTel auto-instrumentation)
        # Tự động capture: model name, input/output tokens, cost
        try:
            from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
            AnthropicInstrumentor().instrument()
            print("   ✅ [LANGFUSE] AnthropicInstrumentor active — model/tokens auto-captured")
        except ImportError:
            print("   ⚠️ [LANGFUSE] opentelemetry-instrumentation-anthropic chưa cài. Chạy: pip install opentelemetry-instrumentation-anthropic")
            print("   ℹ️ [LANGFUSE] Fallback: dùng manual generation logging")

        _langfuse_initialized = True
        print(f"   ✅ [LANGFUSE] Tracing active → {host}")
        return True

    except ImportError:
        print("   ⚠️ [LANGFUSE] Package chưa cài. Chạy: pip install langfuse")
        return False
    except Exception as e:
        print(f"   ⚠️ [LANGFUSE] Init error: {e}")
        return False


def get_langfuse() -> Any | None:
    """Lấy Langfuse singleton client."""
    return _langfuse_client


def flush_traces() -> None:
    """Flush pending traces — gọi khi shutdown."""
    if _langfuse_client:
        try:
            _langfuse_client.flush()
            print("   ✅ [LANGFUSE] Traces flushed.")
        except Exception as e:
            print(f"   ⚠️ [LANGFUSE] Flush error: {e}")


# === Utility: PII Masking ===

def mask_email(email: str) -> str:
    """Mask email để tránh PII leakage trong traces."""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    masked_local = local[:2] + "***" if len(local) > 2 else "***"
    return f"{masked_local}@{domain}"


def mask_sensitive_text(text: str) -> str:
    """Mask email addresses trong text trước khi gửi vào trace."""
    return re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        lambda m: mask_email(m.group(0)),
        text
    )


# === Context helpers cho @observe decorator ===

def get_observe_context(
    user_id: str,
    channel: str,
    role: str,
    session_id: str | None = None,
) -> dict:
    """
    Tạo context dict cho @observe decorator.
    Tags và metadata theo best practices:
    - user_id: per-user cost attribution
    - session_id: group conversation turns
    - tags: channel + role cho business-level filtering
    """
    tags = [f"channel:{channel}", f"role:{role}", "smartshop"]
    return {
        "user_id": mask_email(str(user_id)) if "@" not in str(user_id) else mask_email(str(user_id)),
        "session_id": session_id or f"{channel}-{user_id}",
        "tags": tags,
        "metadata": {
            "channel": channel,
            "role": role,
            "service": "smartshop-odoo-ai-gateway",
        }
    }
