"""
SmartShop Enterprise AI Gateway — Main Entrypoint (v2.0 Multi-Layer Architecture)
=================================================================================
KIẾN TRÚC 6 TẦNG:
  Layer 1: Channels    → Telegram + Odoo Live Chat + API Webhook
  Layer 2: Gateway     → Auth (OTP/RBAC) + Rate Limit + Idempotency
  Layer 3: Agents      → Recommendation → Validation → Fulfillment
  Layer 4: Skills      → Sales, Inventory, Accounting (JIT loading)
  Layer 5: MCP         → Odoo MCP (erpipe-org) + 30min Cache + Fallback
  Layer 6: Observability → LangFuse Cost Tracking + Odoo Chatter Audit
=================================================================================
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

load_env()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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
from observability import get_tracker, get_audit_logger

# ------------------------------------------------------------------
# FastAPI App
# ------------------------------------------------------------------
app = FastAPI(
    title="SmartShop Enterprise AI Gateway",
    description="Multi-Channel AI Gateway for Odoo 19 SaaS Enterprise",
    version="2.0.0"
)

# Mount Webhook Channel router
app.include_router(webhook_router)


@app.get("/")
def read_root():
    return {
        "service": "SmartShop Enterprise AI Gateway v2.0",
        "architecture": "6-Layer Multi-Channel",
        "channels": ["Telegram", "Odoo Live Chat", "API Webhook"],
        "status": "online",
        "health": "healthy"
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0"}


@app.get("/metrics")
def get_metrics():
    """Endpoint metrics cho monitoring (LangFuse + MCP cache stats)."""
    tracker = get_tracker()
    return {
        "session_stats": tracker.get_session_stats(),
        "rate_limiter": "active"
    }


# ------------------------------------------------------------------
# Core Message Handler (shared across all channels)
# ------------------------------------------------------------------

# Global agents
_recommendation_agent = RecommendationAgent()
_validation_agent = ValidationAgent()
_fulfillment_agent = FulfillmentAgent()

# Global MCP wrapper (set sau khi MCP session khởi động)
_mcp_wrapper: MCPClientWrapper | None = None


async def handle_message(channel_msg) -> str:
    """
    Central message handler — nhận ChannelMessage từ bất kỳ channel nào,
    chạy qua Gateway → Agent Pipeline → trả về response text.
    """
    from channels.base_channel import ChannelMessage

    user_id = channel_msg.user_id
    text = channel_msg.text
    channel = channel_msg.channel

    tracker = get_tracker()
    trace = tracker.start_trace(
        user_id=user_id,
        channel=channel,
        input_text=text
    )

    # Layer 2: Auth Gateway
    gateway = SecurityGateway()

    # Bỏ qua auth check cho callback queries
    if channel_msg.metadata.get("type") == "callback_query":
        # Xử lý approve/reject callback
        return await _handle_approval_callback(text, user_id)

    auth = gateway.process_incoming_request(user_id, text)
    if not auth["allowed"]:
        return auth["reason"]

    user_info = auth

    # Layer 3: Agent Pipeline
    if _mcp_wrapper is None:
        return "⚠️ MCP session chưa sẵn sàng. Vui lòng thử lại sau vài giây."

    # Bước 1: Recommendation Agent
    rec_span = trace.span("recommendation", text)
    rec_result = await _recommendation_agent.execute(
        user_id, text, user_info, _mcp_wrapper
    )
    rec_span.finish(rec_result.response[:200])

    # Nếu không cần tạo đơn → trả lời ngay
    if rec_result.next_agent is None:
        trace.finish(rec_result.response[:500])
        return rec_result.response

    # Bước 2: Fulfillment Agent (khi user muốn tạo đơn)
    if rec_result.next_agent == "fulfillment":
        # Validation trước
        val_result = await _validation_agent.execute(
            user_id, text, user_info, _mcp_wrapper,
            context=rec_result.metadata
        )

        if not val_result.success or val_result.needs_approval:
            trace.finish(val_result.response[:500])
            return val_result.response

        # Fulfillment
        ful_span = trace.span("fulfillment", text)
        ful_result = await _fulfillment_agent.execute(
            user_id, text, user_info, _mcp_wrapper,
            context=val_result.metadata
        )
        ful_span.finish(ful_result.response[:200])
        trace.finish(ful_result.response[:500])
        return ful_result.response

    trace.finish(rec_result.response[:500])
    return rec_result.response


async def _handle_approval_callback(callback_data: str, approver_id: str) -> str:
    """Xử lý nút bấm Approve/Reject từ Telegram Inline Keyboard."""
    from auth_gateway import verify_approval_token
    parts = callback_data.split("_")
    if len(parts) < 3:
        return "❌ Callback không hợp lệ."

    action = parts[0]  # "approve" hoặc "reject"
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
# Bot Runners (chạy trong background threads)
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
                print(f"✅ [MCP] Session ready! Cache TTL=30min, Fallback=active")

                from channels.telegram_channel import TelegramChannel
                telegram = TelegramChannel()
                await telegram.run(handle_message)

    try:
        asyncio.run(_telegram_loop())
    except Exception as e:
        print(f"❌ [TELEGRAM BOT ERROR]: {e}")


def run_livechat_bot():
    """Chạy Odoo Live Chat Channel trong thread riêng (không cần MCP session)."""
    async def _livechat_loop():
        # Live Chat dùng OdooClient trực tiếp (không qua MCP)
        # Chờ MCP wrapper sẵn sàng trước
        import time
        for _ in range(30):  # Chờ tối đa 30 giây
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
    """Đăng ký handler cho Webhook Channel (không cần thread riêng — FastAPI xử lý)."""
    from channels.webhook_channel import WebhookChannel
    webhook = WebhookChannel()

    async def _sync_handle(msg):
        return await handle_message(msg)

    # Set async handler — webhook channel chạy trong FastAPI event loop
    import asyncio

    async def _async_setup():
        webhook.set_handler(handle_message)

    # Schedule setup sau khi FastAPI starts
    return webhook


# ------------------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("  SMARTSHOP ENTERPRISE AI GATEWAY v2.0 — 6-LAYER ARCHITECTURE")
    print("=" * 70)
    print("  Layer 1: Telegram + Odoo Live Chat + API Webhook")
    print("  Layer 2: Auth (OTP/RBAC) + Rate Limit (30 req/min) + Idempotency")
    print("  Layer 3: Recommendation → Validation → Fulfillment Agents")
    print("  Layer 4: Sales + Inventory + Accounting Skills (JIT)")
    print("  Layer 5: Odoo MCP + 30min TTL Cache + Fallback")
    print("  Layer 6: LangFuse Cost Tracking + Odoo Chatter Audit")
    print("=" * 70)

    # Khởi động Telegram Bot (có MCP session) trong background thread
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()

    # Khởi động Odoo Live Chat Bot trong background thread
    livechat_thread = threading.Thread(target=run_livechat_bot, daemon=True)
    livechat_thread.start()

    # Đăng ký Webhook handler
    setup_webhook_channel()

    # Khởi động FastAPI Web Server (main thread — Render health checks)
    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Web Gateway starting on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
