"""
Telegram Channel — Tầng 1: Multi-Channel Interface
Kênh Telegram 24/7 Mobile Chat.
Refactor từ telegram_bot_listener.py — tách clean khỏi Agent logic.

Architecture:
- TelegramChannel chịu trách nhiệm: poll updates, send/receive messages, parse commands
- Mọi AI processing đều delegate sang Gateway → Agents pipeline
"""

from __future__ import annotations
import os
import json
import asyncio
import urllib.request
from typing import Callable, Awaitable

from .base_channel import BaseChannel, ChannelMessage
from gateway import SecurityGateway, RateLimiter, IdempotencyGuard, get_rate_limiter
from gateway.idempotency import get_idempotency_guard, should_dedup

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

ADMIN_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6553206564")

# Lệnh hệ thống — xử lý riêng, không đưa qua AI pipeline
SYSTEM_COMMANDS = {"/start", "/register", "/verify", "/my_role", "/clear", "/reset", "/help"}


class TelegramChannel(BaseChannel):
    """
    Telegram Bot Channel — polling-based, 24/7 uptime.
    Tích hợp Rate Limiter và Idempotency Guard từ Gateway layer.
    """

    def __init__(self):
        super().__init__(name="telegram")
        self._gateway = SecurityGateway()
        self._rate_limiter: RateLimiter = get_rate_limiter()
        self._idempotency: IdempotencyGuard = get_idempotency_guard()
        self._offset = 0

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    async def send_message(
        self,
        user_id: str,
        text: str,
        metadata: dict | None = None,
        parse_mode: str | None = "Markdown"
    ) -> bool:
        """Gửi tin nhắn về Telegram (Hỗ trợ nút bấm Inline Keyboards tự động)."""
        url = f"{BASE_URL}/sendMessage"

        reply_markup = None
        if metadata and metadata.get("reply_markup"):
            reply_markup = metadata["reply_markup"]

        # Tự động bóc tách cờ [INLINE_KEYBOARD] từ response text
        if "[INLINE_KEYBOARD]" in text:
            match = re.search(r'\[INLINE_KEYBOARD\]\s*(.*)', text, re.DOTALL)
            if match:
                try:
                    kb_buttons = json.loads(match.group(1).strip())
                    reply_markup = {"inline_keyboard": kb_buttons}
                    text = text.replace(match.group(0), "").strip()
                except Exception as e:
                    print(f"⚠️ [TelegramChannel] Lỗi parse INLINE_KEYBOARD: {e}")

        payload = {
            "chat_id": user_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        encoded = json.dumps(payload).encode("utf-8")
        try:
            req = urllib.request.Request(
                url, data=encoded,
                headers={"Content-Type": "application/json"}
            )
            await asyncio.to_thread(
                lambda: urllib.request.urlopen(req, timeout=8).read()
            )
            return True
        except Exception as e:
            print(f"[TELEGRAM SEND FAILED] {user_id}: {e}")
            if parse_mode:
                return await self.send_message(user_id, text, metadata, parse_mode=None)
            return False

    async def run(self, message_handler: Callable[[ChannelMessage], Awaitable[str]]) -> None:
        """
        Main event loop: poll Telegram getUpdates và dispatch tới message_handler.
        message_handler: async function nhận ChannelMessage, trả về response text.
        """
        self._running = True
        print(f"✅ [{self.name.upper()} CHANNEL] Polling started.")

        while self._running:
            try:
                updates = await self._poll_updates()
                for update in updates:
                    self._offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    chat = msg.get("chat", {})
                    user_id = str(chat.get("id", ""))
                    text = msg.get("text", "").strip()
                    callback = update.get("callback_query", {})

                    # Xử lý Callback Query (nút bấm Approve/Reject)
                    if callback:
                        await self._handle_callback(callback, message_handler)
                        continue

                    if not user_id or not text:
                        continue

                    # Xử lý lệnh hệ thống ngay tại channel layer
                    if any(text.lower().startswith(cmd) for cmd in SYSTEM_COMMANDS):
                        await self._handle_system_command(user_id, text)
                        continue

                    # Rate limiting
                    allowed, rate_info = self._rate_limiter.is_allowed(user_id)
                    if not allowed:
                        await self.send_message(user_id, rate_info["message"])
                        continue

                    # Idempotency check
                    if should_dedup(text):
                        is_dup, cached = self._idempotency.check(user_id, text)
                        if is_dup and cached:
                            await self.send_message(user_id, cached)
                            continue

                    # Đưa vào AI pipeline
                    channel_msg = ChannelMessage(
                        channel="telegram",
                        user_id=user_id,
                        text=text,
                        raw=update,
                        metadata={"chat_id": user_id}
                    )
                    try:
                        response = await message_handler(channel_msg)
                        if response:
                            await self.send_message(user_id, response)
                            # Cache response cho dedup
                            if should_dedup(text):
                                self._idempotency.store(user_id, text, response)
                    except Exception as ex:
                        print(f"   ❌ [HANDLER ERROR] {ex}")
                        await self.send_message(user_id, f"❌ Lỗi xử lý: {str(ex)[:150]}")

                await asyncio.sleep(1)
            except Exception as e:
                print(f"   ⚠️ [POLL ERROR]: {e}")
                await asyncio.sleep(2)

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    async def _poll_updates(self) -> list[dict]:
        """Gọi Telegram getUpdates API."""
        url = f"{BASE_URL}/getUpdates?offset={self._offset}&timeout=10"
        try:
            data = await asyncio.to_thread(
                lambda: json.loads(urllib.request.urlopen(url, timeout=12).read().decode("utf-8"))
            )
            return data.get("result", [])
        except Exception:
            return []

    async def _handle_system_command(self, user_id: str, text: str) -> None:
        """Xử lý các lệnh hệ thống: /register, /verify, /my_role, /clear."""
        lower = text.lower()

        if lower == "/start" or lower == "/help":
            await self.send_message(user_id, self._get_welcome_message())
            return

        if lower.startswith("/register"):
            parts = text.split()
            if len(parts) < 2:
                await self.send_message(user_id, "Cu phap: /register email_cua_ban@gmail.com", parse_mode=None)
                return
            ok, msg = self._gateway.request_otp(user_id, parts[1].lower().strip())
            await self.send_message(user_id, msg.replace("`", "").replace("**", ""), parse_mode=None)
            return

        if lower.startswith("/verify"):
            parts = text.split()
            if len(parts) < 2:
                await self.send_message(user_id, "Cu phap: /verify MA_OTP_6_SO", parse_mode=None)
                return
            ok, msg = self._gateway.verify_otp_and_bind(user_id, parts[1].strip())
            await self.send_message(user_id, msg.replace("`", "").replace("**", ""), parse_mode=None)
            return

        if lower == "/my_role":
            from gateway.services.odoo_role_context_service import OdooRoleContextService
            OdooRoleContextService.clear_cache()
            auth = self._gateway.process_incoming_request(user_id)
            if not auth["allowed"]:
                await self.send_message(user_id, auth["reason"], parse_mode=None)
            else:
                u = auth["user_info"]
                groups = u.get("odoo_groups", [])
                g_str = "\n".join(f"  • {g}" for g in groups) if groups else "  • (Không có)"
                role_name = u.get("role", u.get("role_category", "user"))
                await self.send_message(user_id,
                    f"👤 THÔNG TIN TÀI KHOẢN ODOO SAAS\n"
                    f"• Họ tên: {u.get('full_name')}\n"
                    f"• Email: {u.get('email')}\n"
                    f"• Vai trò chính: {role_name.upper()}\n\n"
                    f"📋 Nhóm quyền Odoo Live:\n{g_str}",
                    parse_mode=None
                )
            return

        if lower in ("/clear", "/reset"):
            from gateway.services.odoo_role_context_service import OdooRoleContextService
            OdooRoleContextService.clear_cache()
            await self.send_message(user_id, "🧹 Đã xóa bộ nhớ hội thoại và làm mới Cache quyền Odoo SaaS!", parse_mode=None)
            return

    async def _handle_callback(
        self,
        callback: dict,
        message_handler: Callable
    ) -> None:
        """Xử lý nút bấm Approve/Reject từ Inline Keyboard."""
        callback_id = callback.get("id", "")
        data = callback.get("data", "")
        from_user = callback.get("from", {})
        user_id = str(from_user.get("id", ""))

        # Answer callback để xóa loading spinner
        try:
            ack_url = f"{BASE_URL}/answerCallbackQuery"
            ack_payload = json.dumps({"callback_query_id": callback_id}).encode("utf-8")
            req = urllib.request.Request(
                ack_url, data=ack_payload,
                headers={"Content-Type": "application/json"}
            )
            await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=5).read())
        except Exception:
            pass

        # Chuyển đổi callback action thành câu lệnh tự nhiên cho AI
        text_action = data
        if data.startswith("action:draft_order:"):
            prod_id = data.split(":")[-1]
            text_action = f"Tạo đơn hàng nháp cho sản phẩm số {prod_id}"
        elif data.startswith("action:check_stock:"):
            prod_id = data.split(":")[-1]
            text_action = f"Kiểm tra tồn kho sản phẩm số {prod_id}"
        elif data == "action:view_draft":
            text_action = "Xem đơn hàng nháp hiện tại"

        # Delegate tới message_handler với context callback
        channel_msg = ChannelMessage(
            channel="telegram",
            user_id=user_id,
            text=text_action,
            raw=callback,
            metadata={"type": "callback_query", "callback_data": data}
        )
        try:
            response = await message_handler(channel_msg)
            if response and user_id:
                await self.send_message(user_id, response)
        except Exception as ex:
            print(f"   ❌ [CALLBACK ERROR]: {ex}")

    async def _send_startup_message(self) -> None:
        """Gửi welcome + hướng dẫn onboarding khi bot khởi động."""
        msg = (
            "🛍️ *CHÀO MỪNG ĐẾN VỚI TRỢ LÝ AI SMARTSHOP ODOO 19*\n\n"
            "🔒 Để đảm bảo an toàn dữ liệu doanh nghiệp, vui lòng kích hoạt tài khoản:\n\n"
            "1️⃣ Đăng ký Email nhân viên:\n"
            "`/register email_cua_ban@company.com`\n\n"
            "2️⃣ Nhập mã OTP được gửi về Email:\n"
            "`/verify 123456`\n\n"
            "💡 *Sau khi kích hoạt, bạn có thể tra cứu tồn kho, giá bán và tạo báo giá trực tiếp!*"
        )
        await self.send_message(ADMIN_CHAT_ID, msg)

    @staticmethod
    def _get_welcome_message() -> str:
        return (
            "👋 *SMARTSHOP AI ASSISTANT*\n\n"
            "Tôi có thể giúp bạn:\n"
            "• 🔍 Tra cứu sản phẩm & giá bán\n"
            "• 📦 Kiểm tra tồn kho\n"
            "• 📋 Tạo báo giá & đơn hàng\n"
            "• 📊 Xem công nợ khách hàng\n\n"
            "📌 *Lệnh hữu ích:*\n"
            "`/register` — Đăng ký tài khoản\n"
            "`/verify` — Xác thực OTP\n"
            "`/my_role` — Xem quyền hạn\n"
            "`/clear` — Xóa bộ nhớ hội thoại"
        )
