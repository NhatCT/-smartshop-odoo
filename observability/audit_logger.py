"""
Audit Logger — Tầng 6: Observability
Ghi audit trail vào Odoo Chatter (message_post) — Single Source of Truth.
Mọi thao tác AI (query, tạo đơn, phê duyệt) đều được ghi vết vào Odoo.
"""

from __future__ import annotations
import asyncio
import time
from typing import Any
from odoo_client import OdooClient


class AuditEvent:
    """Enum-style constants cho audit event types."""
    QUERY = "QUERY"               # User tra cứu thông tin
    ORDER_CREATE = "ORDER_CREATE" # Tạo đơn hàng
    ORDER_CONFIRM = "ORDER_CONFIRM"  # Xác nhận đơn hàng
    APPROVAL_REQUEST = "APPROVAL_REQUEST"  # Gửi yêu cầu phê duyệt
    APPROVAL_DONE = "APPROVAL_DONE"    # Phê duyệt thành công
    APPROVAL_REJECT = "APPROVAL_REJECT"   # Từ chối đơn hàng
    AUTH_FAIL = "AUTH_FAIL"       # Đăng nhập thất bại
    RATE_LIMIT = "RATE_LIMIT"     # Bị rate limit


class AuditLogger:
    """
    Odoo Chatter Audit Logger.
    Ghi nhật ký AI actions vào Odoo `mail.message` qua `message_post`.
    Không cần DB riêng — tận dụng Odoo là Single Source of Truth.
    """

    def __init__(self):
        self._odoo = OdooClient()
        self._buffer: list[dict] = []  # Buffer để batch write
        self._last_flush = time.time()

    async def log(
        self,
        event_type: str,
        user_name: str,
        user_role: str,
        channel: str,
        record_model: str | None = None,
        record_id: int | None = None,
        summary: str = "",
        details: str = ""
    ) -> None:
        """
        Ghi audit log.
        Nếu có record_model + record_id → ghi vào Chatter của record đó.
        Nếu không → log ra console (fallback).
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "event": event_type,
            "user": user_name,
            "role": user_role,
            "channel": channel,
            "summary": summary,
            "time": timestamp
        }

        # Console log luôn
        print(f"   📋 [AUDIT] {event_type} | {user_name} ({channel}) | {summary[:80]}")

        # Ghi vào Odoo Chatter nếu có record
        if record_model and record_id:
            await self._write_chatter(
                record_model=record_model,
                record_id=record_id,
                event_type=event_type,
                user_name=user_name,
                user_role=user_role,
                channel=channel,
                summary=summary,
                details=details,
                timestamp=timestamp
            )

    async def _write_chatter(
        self,
        record_model: str,
        record_id: int,
        event_type: str,
        user_name: str,
        user_role: str,
        channel: str,
        summary: str,
        details: str,
        timestamp: str
    ) -> None:
        """Ghi vào Odoo Chatter của record cụ thể."""
        channel_icon = {
            "telegram": "📱", "livechat": "💬",
            "webhook": "🔗", "slack": "💼"
        }.get(channel, "🤖")

        event_label = {
            AuditEvent.ORDER_CREATE: "✅ Tạo đơn hàng",
            AuditEvent.ORDER_CONFIRM: "✔️ Xác nhận đơn hàng",
            AuditEvent.APPROVAL_REQUEST: "⏳ Gửi yêu cầu phê duyệt",
            AuditEvent.APPROVAL_DONE: "✅ Phê duyệt thành công",
            AuditEvent.APPROVAL_REJECT: "❌ Từ chối đơn hàng",
            AuditEvent.QUERY: "🔍 Tra cứu thông tin",
        }.get(event_type, event_type)

        body = (
            f"<b>{channel_icon} AI SmartShop — {event_label}</b><br/>"
            f"<b>Nhân viên:</b> {user_name} ({user_role})<br/>"
            f"<b>Kênh:</b> {channel.capitalize()}<br/>"
            f"<b>Thao tác:</b> {summary}<br/>"
            f"<b>Thời gian:</b> {timestamp}"
        )
        if details:
            body += f"<br/><b>Chi tiết:</b> {details[:300]}"

        try:
            await asyncio.to_thread(
                lambda: self._odoo.execute_method(
                    record_model, "message_post",
                    [record_id],
                    **{
                        "body": body,
                        "message_type": "comment",
                        "subtype_xmlid": "mail.mt_note"
                    }
                )
            )
        except Exception as e:
            print(f"   ⚠️ [AUDIT CHATTER FAILED] {record_model}/{record_id}: {e}")


# Singleton
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
