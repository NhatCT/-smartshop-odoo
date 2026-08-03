"""
Webhook Channel — Tầng 1: Multi-Channel Interface
REST API Webhook channel cho n8n, custom integrations, và direct API access.
Expose endpoint POST /webhook để nhận messages từ bên ngoài.
"""

from __future__ import annotations
from typing import Callable, Awaitable
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import asyncio
import os

from .base_channel import BaseChannel, ChannelMessage
from gateway import SecurityGateway, RateLimiter, get_rate_limiter
from gateway.idempotency import get_idempotency_guard, should_dedup

# FastAPI Router — được mount vào app_entrypoint.py
webhook_router = APIRouter(prefix="/webhook", tags=["Webhook Channel"])

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


class WebhookPayload(BaseModel):
    """Chuẩn payload JSON cho Webhook requests."""
    user_id: str
    message: str
    channel: str = "webhook"
    idempotency_key: str | None = None
    metadata: dict = {}


class WebhookResponse(BaseModel):
    """Chuẩn response cho Webhook."""
    success: bool
    response: str
    user_id: str
    cached: bool = False


# Global message handler — được set bởi WebhookChannel.set_handler()
_message_handler: Callable | None = None


@webhook_router.post("/", response_model=WebhookResponse)
async def receive_webhook(
    payload: WebhookPayload,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret")
):
    """
    Endpoint nhận messages từ n8n, API clients, hoặc custom integrations.
    Header X-Webhook-Secret phải khớp với WEBHOOK_SECRET env (nếu đã đặt).
    """
    # Auth check
    if WEBHOOK_SECRET and x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    if not _message_handler:
        raise HTTPException(status_code=503, detail="Message handler not initialized")

    rate_limiter = get_rate_limiter()
    idempotency = get_idempotency_guard()

    # Rate limiting
    allowed, rate_info = rate_limiter.is_allowed(payload.user_id)
    if not allowed:
        return WebhookResponse(
            success=False,
            response=rate_info["message"],
            user_id=payload.user_id
        )

    # Idempotency check
    if should_dedup(payload.message):
        is_dup, cached = idempotency.check(payload.user_id, payload.message)
        if is_dup and cached:
            return WebhookResponse(
                success=True,
                response=cached,
                user_id=payload.user_id,
                cached=True
            )

    channel_msg = ChannelMessage(
        channel=payload.channel,
        user_id=payload.user_id,
        text=payload.message,
        raw=payload.dict(),
        metadata=payload.metadata
    )

    try:
        response = await _message_handler(channel_msg)
        if should_dedup(payload.message) and response:
            idempotency.store(payload.user_id, payload.message, response)
        return WebhookResponse(
            success=True,
            response=response or "",
            user_id=payload.user_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@webhook_router.get("/health")
async def webhook_health():
    """Health check cho webhook endpoint."""
    return {"status": "ok", "handler_ready": _message_handler is not None}


class WebhookChannel(BaseChannel):
    """
    Webhook Channel — REST API interface cho n8n và custom integrations.
    Không chạy event loop riêng — sử dụng FastAPI router được mount vào app.
    """

    def __init__(self):
        super().__init__(name="webhook")

    def set_handler(self, handler: Callable[[ChannelMessage], Awaitable[str]]) -> None:
        """Đăng ký message handler cho webhook endpoint."""
        global _message_handler
        _message_handler = handler
        self._running = True
        print(f"✅ [{self.name.upper()} CHANNEL] Handler registered.")

    async def send_message(self, user_id: str, text: str, metadata: dict | None = None) -> bool:
        """
        Webhook channel không push messages (request-response pattern).
        Response được trả về trực tiếp qua HTTP response.
        """
        return True  # No-op — response handled by HTTP

    async def run(self, message_handler: Callable) -> None:
        """
        Webhook không cần polling — FastAPI xử lý request routing.
        Chỉ đăng ký handler và đợi.
        """
        self.set_handler(message_handler)
        # Keep alive — run() không return để giống interface với other channels
        while self._running:
            await asyncio.sleep(60)
