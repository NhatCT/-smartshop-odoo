"""
SmartShop Enterprise AI Gateway — Main Entrypoint (v2.1 + Langfuse Tracing)
=============================================================================
KIẾN TRÚC 6 TẦNG:
  Layer 1: Channels    → Telegram + Odoo Live Chat + API Webhook
  Layer 2: Gateway     → Auth (OTP/RBAC) + Rate Limit + Idempotency
  Layer 3: Agents      → Recommendation → Validation → Fulfillment
  Layer 4: Skills      → Sales, Inventory, Accounting (JIT loading)
  Layer 5: MCP         → Odoo MCP (erpipe-org) + 30min Cache + Fallback
  Layer 6: Observability → Langfuse Tracing + Odoo Chatter Audit

IMPORT ORDER (BẮT BUỘC theo Langfuse Skill):
  1. os, sys, threading, asyncio
  2. load_env()  ← load .env trước
  3. setup_langfuse_tracing()  ← init Langfuse & AnthropicInstrumentor TRƯỚC anthropic
  4. tất cả imports khác
=============================================================================
"""

import os
import sys
import threading
import asyncio
from dotenv_loader import load_env

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# BƯỚC 1: Load .env trước tất cả
load_env()

# BƯỚC 2: Setup Langfuse + AnthropicInstrumentor TRƯỚC KHI import anthropic
# (Per Langfuse Skill: "Import Langfuse AFTER loading environment variables,
#  Import Langfuse and call its setup BEFORE importing OpenAI/Anthropic client")
from observability.langfuse_setup import setup_langfuse_tracing, flush_traces, mask_sensitive_text, get_observe_context
_langfuse_active = setup_langfuse_tracing()

# BƯỚC 3: Sau đó mới import các module còn lại
from fastapi import FastAPI
import uvicorn

# Layer 1: Channel imports
from channels.webhook_channel import webhook_router

# Layer 2: Gateway
from gateway import SecurityGateway, get_rate_limiter

# Layer 5: MCP imports (lazy — thực hiện trong async context)
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp_layer import MCPClientWrapper

# Layer 3: Agents
from agents import RecommendationAgent, ValidationAgent, FulfillmentAgent

# Layer 6: Observability
from observability import get_audit_logger

# ------------------------------------------------------------------
# FastAPI App
# ------------------------------------------------------------------
app = FastAPI(
    title="SmartShop Enterprise AI Gateway",
    description="Multi-Channel AI Gateway for Odoo 19 SaaS Enterprise",
    version="2.1.0"
)

# Mount Webhook Channel router
app.include_router(webhook_router)


@app.get("/")
def read_root():
    return {
        "service": "SmartShop Enterprise AI Gateway v2.1",
        "architecture": "6-Layer Multi-Channel + Langfuse Tracing",
        "channels": ["Telegram", "Odoo Live Chat", "API Webhook"],
        "status": "online",
        "langfuse_tracing": _langfuse_active,
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.1"}


@app.get("/metrics")
def get_metrics():
    """Metrics endpoint cho monitoring — Langfuse + MCP cache stats."""
    from observability.langfuse_setup import get_langfuse
    lf = get_langfuse()
    return {
        "langfuse_active": _langfuse_active,
        "mcp_ready": _mcp_wrapper is not None,
    }


@app.on_event("shutdown")
async def on_shutdown():
    """Flush Langfuse traces khi server shutdown — tránh mất traces."""
    flush_traces()


# ------------------------------------------------------------------
# Core Message Handler — @observe decorated cho Langfuse tracing
# ------------------------------------------------------------------

# Global agents — singleton
_recommendation_agent = RecommendationAgent()
_validation_agent = ValidationAgent()
_fulfillment_agent = FulfillmentAgent()

# Global MCP wrapper (set sau khi MCP session khởi động)
_mcp_wrapper: MCPClientWrapper | None = None


try:
    from langfuse.decorators import observe
except ImportError:
    def observe(*args, **kwargs):
        return lambda f: f

@observe()
async def handle_message(channel_msg) -> str:
    """
    Central message handler với Langfuse @observe tracing.

    Trace structure (theo best practices):
    - Trace: "smartshop-chat-turn" (1 trace per turn, per channel)
      - user_id: masked (no PII leak)
      - session_id: channel+user_id (groups turns per conversation)
      - tags: ["channel:telegram", "role:sales_staff", "smartshop"]
      - input: user message text (clean, not full args dump)
      - output: final assistant response
    """
    user_id = channel_msg.user_id
    text = channel_msg.text
    channel = channel_msg.channel

    # Xử lý callback query ngay (không cần tracing)
    if channel_msg.metadata.get("type") == "callback_query":
        return await _handle_approval_callback(text, user_id)

    # Layer 2: Auth Gateway
    gateway = SecurityGateway()
    auth = gateway.process_incoming_request(user_id, text)
    if not auth["allowed"]:
        return auth["reason"]

    user_info = auth
    role = user_info.get("official_role", "viewer")

    obs_ctx = get_observe_context(user_id, channel, role)

    if _langfuse_active:
        from langfuse import propagate_attributes, get_client
        
        # Propagate attributes (v4 SDK pattern)
        with propagate_attributes(
            user_id=obs_ctx["user_id"],
            session_id=obs_ctx["session_id"],
            tags=obs_ctx["tags"],
            trace_name="smartshop-chat-turn"
        ):
            return await _traced_handle_message(channel_msg, obs_ctx)
    else:
        return await _traced_handle_message(channel_msg, obs_ctx)

try:
    from langfuse import observe, get_client
except ImportError:
    def observe(*args, **kwargs):
        return lambda f: f
    def get_client(*args, **kwargs):
        return None

@observe()
async def _traced_handle_message(channel_msg, obs_ctx) -> str:
    user_id = channel_msg.user_id
    text = channel_msg.text
    channel = channel_msg.channel

    langfuse = get_client()
    if langfuse:
        try:
            from observability.langfuse_setup import mask_sensitive_text
            langfuse.update_current_span(
                input=mask_sensitive_text(text[:500])
            )
        except Exception:
            pass

    # Layer 3: Agent Pipeline
    if _mcp_wrapper is None:
        response = "⚠️ MCP session chưa sẵn sàng. Vui lòng thử lại sau vài giây."
        _update_trace_output(response)
        return response

    # Agent context (truyền channel cho recommendation agent tracing)
    agent_context = {"channel": channel}

    # Bước 1: Recommendation Agent — span type "agent" (multi-agent subagent rule)
    if _langfuse_active:
        try:
            from langfuse import get_client
            lf_client = get_client()
            if lf_client:
                lf_client.update_current_span(name="recommend-products")
        except Exception:
            pass

    rec_result = await _recommendation_agent.execute(
        user_id, text, user_info, _mcp_wrapper, context=agent_context
    )

    if rec_result.next_agent is None:
        _update_trace_output(rec_result.response)
        return rec_result.response

    # Bước 2: Validation Agent
    if rec_result.next_agent == "fulfillment":
        val_result = await _validation_agent.execute(
            user_id, text, user_info, _mcp_wrapper,
            context=rec_result.metadata
        )

        if not val_result.success or val_result.needs_approval:
            _update_trace_output(val_result.response)
            return val_result.response

        # Bước 3: Fulfillment Agent
        ful_result = await _fulfillment_agent.execute(
            user_id, text, user_info, _mcp_wrapper,
            context=val_result.metadata
        )
        _update_trace_output(ful_result.response)
        return ful_result.response

    _update_trace_output(rec_result.response)
    return rec_result.response


def _update_trace_output(response: str) -> None:
    """Cập nhật output của trace hiện tại (per best practices: root trace có output)."""
    if not _langfuse_active:
        return
    try:
        from langfuse import get_client
        lf_client = get_client()
        if lf_client:
            lf_client.update_current_span(output=response[:500])
    except Exception:
        pass


async def _handle_approval_callback(callback_data: str, approver_id: str) -> str:
    """Xử lý nút bấm Approve/Reject từ Telegram Inline Keyboard."""
    from auth_gateway import verify_approval_token
    parts = callback_data.split("_")
    if len(parts) < 3:
        return "❌ Callback không hợp lệ."

    action = parts[0]
    order_name = "_".join(parts[1:-1])
    token = parts[-1]

    if not verify_approval_token(order_name, approver_id, token):
        return "⛔ Token xác thực không hợp lệ. Thao tác bị từ chối."

    if action == "approve":
        return f"✅ **{order_name}** đã được PHÊDUYỆT bởi Manager!\nHệ thống đang chốt đơn..."
    elif action == "reject":
        return f"❌ **{order_name}** đã bị TỪ CHỐI.\nThông báo sẽ được gửi lại cho nhân viên."
    return "❓ Hành động không xác định."


# ------------------------------------------------------------------
# Bot Runners
# ------------------------------------------------------------------

def run_telegram_bot():
    """Chạy Telegram Channel trong async event loop riêng."""
    async def _telegram_loop():
        global _mcp_wrapper
        print("🤖 [TELEGRAM] Starting bot + MCP session...")

        server_params = StdioServerParameters(
            command="python",
            args=["-m", "odoo_mcp"],
            env=dict(os.environ)
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                _mcp_wrapper = MCPClientWrapper(session)
                print("✅ [MCP] Session ready! Cache TTL=30min, Fallback=active")

                from channels.telegram_channel import TelegramChannel
                telegram = TelegramChannel()
                await telegram.run(handle_message)

    try:
        asyncio.run(_telegram_loop())
    except Exception as e:
        print(f"❌ [TELEGRAM BOT ERROR]: {e}")
    finally:
        # Flush traces khi Telegram bot shutdown
        flush_traces()


def run_livechat_bot():
    """Chạy Odoo Live Chat Channel trong thread riêng."""
    async def _livechat_loop():
        import time
        for _ in range(30):
            if _mcp_wrapper is not None:
                break
            await asyncio.sleep(1)

        from channels.livechat_channel import LiveChatChannel
        livechat = LiveChatChannel()
        await livechat.run(handle_message)

    try:
        asyncio.run(_livechat_loop())
    except Exception as e:
        print(f"❌ [LIVECHAT BOT ERROR]: {e}")


def setup_webhook_channel():
    """Đăng ký handler cho Webhook Channel."""
    from channels.webhook_channel import WebhookChannel
    webhook = WebhookChannel()
    webhook.set_handler(handle_message)
    return webhook


# ------------------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("  SMARTSHOP ENTERPRISE AI GATEWAY v2.1 — 6-LAYER ARCHITECTURE")
    print("=" * 70)
    print("  Layer 1: Telegram + Odoo Live Chat + API Webhook")
    print("  Layer 2: Auth (OTP/RBAC) + Rate Limit (30 req/min) + Idempotency")
    print("  Layer 3: Recommendation → Validation → Fulfillment Agents")
    print("  Layer 4: Sales + Inventory + Accounting Skills (JIT)")
    print("  Layer 5: Odoo MCP + 30min TTL Cache + Fallback")
    print(f"  Layer 6: Langfuse Tracing {'✅ ACTIVE' if _langfuse_active else '⚠️ DISABLED'} + Odoo Chatter Audit")
    print("=" * 70)

    # Khởi động Telegram Bot trong background thread
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()

    # Khởi động Odoo Live Chat Bot trong background thread
    livechat_thread = threading.Thread(target=run_livechat_bot, daemon=True)
    livechat_thread.start()

    # Đăng ký Webhook handler
    setup_webhook_channel()

    # Khởi động FastAPI Web Server (main thread)
    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Web Gateway starting on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
