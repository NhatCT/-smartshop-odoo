"""
Odoo Live Chat Channel — Tầng 1: Multi-Channel Interface
Kênh Live Chat nhúng vào Odoo Website (im_livechat).

Cơ chế: Poll Odoo mail.channel qua JSON-RPC để đọc tin nhắn mới,
trả lời bằng message_post. Không cần cài module custom vào Odoo SaaS.

Odoo 19 đã hợp nhất im_livechat với mail.channel — bot hoạt động
hoàn toàn qua Odoo External API chuẩn (GOLDEN RULE #1).
"""

from __future__ import annotations
import asyncio
import time
from typing import Callable, Awaitable

from .base_channel import BaseChannel, ChannelMessage
from odoo_client import OdooClient
from gateway import SecurityGateway

# Polling interval (giây) — đọc tin nhắn mới mỗi 5 giây
LIVECHAT_POLL_INTERVAL = 5

# Prefix để nhận diện tin nhắn từ Bot (tránh echo)
BOT_AUTHOR_PREFIX = "SmartShop AI"


class LiveChatChannel(BaseChannel):
    """
    Odoo Live Chat Channel — poll-based integration.
    
    Cách hoạt động:
    1. Tìm tất cả Live Chat channels đang active trên Odoo
    2. Mỗi 5 giây, poll tin nhắn mới từ mỗi channel
    3. Gửi phản hồi AI bằng message_post trực tiếp vào mail.channel
    4. Track processed message IDs để tránh xử lý lại
    """

    def __init__(self):
        super().__init__(name="livechat")
        self._odoo = OdooClient()
        self._gateway = SecurityGateway()
        self._processed_msg_ids: set[int] = set()
        self._last_check_time = time.time() - LIVECHAT_POLL_INTERVAL
        # Map channel_id → last processed message_id
        self._channel_watermarks: dict[int, int] = {}

    async def send_message(
        self,
        user_id: str,
        text: str,
        metadata: dict | None = None
    ) -> bool:
        """
        Gửi phản hồi vào Odoo Live Chat channel.
        user_id là channel_id của mail.channel.
        """
        channel_id = int(user_id)
        try:
            await asyncio.to_thread(
                lambda: self._odoo.execute_method(
                    "mail.channel", "message_post",
                    [channel_id],
                    **{
                        "body": text.replace("\n", "<br/>"),
                        "message_type": "comment",
                        "subtype_xmlid": "mail.mt_comment"
                    }
                )
            )
            return True
        except Exception as e:
            print(f"   ❌ [LIVECHAT SEND] channel {channel_id}: {e}")
            return False

    async def run(self, message_handler: Callable[[ChannelMessage], Awaitable[str]]) -> None:
        """
        Main event loop: poll Odoo Live Chat channels mỗi 5 giây.
        """
        self._running = True
        print(f"✅ [{self.name.upper()} CHANNEL] Polling Odoo Live Chat every {LIVECHAT_POLL_INTERVAL}s")

        while self._running:
            try:
                await self._poll_and_dispatch(message_handler)
            except Exception as e:
                print(f"   ⚠️ [LIVECHAT POLL ERROR]: {e}")
            await asyncio.sleep(LIVECHAT_POLL_INTERVAL)

    async def _poll_and_dispatch(
        self,
        message_handler: Callable[[ChannelMessage], Awaitable[str]]
    ) -> None:
        """Tìm và xử lý tin nhắn mới từ Live Chat channels."""
        # Tìm live chat channels đang active
        channels = await asyncio.to_thread(
            lambda: self._odoo.search_read(
                "mail.channel",
                domain=[
                    ["channel_type", "=", "livechat"],
                    ["is_member", "=", True]
                ],
                fields=["id", "name", "channel_type"],
                limit=50
            )
        )

        for channel in channels:
            channel_id = channel["id"]
            watermark = self._channel_watermarks.get(channel_id, 0)

            # Lấy tin nhắn mới từ channel này
            messages = await asyncio.to_thread(
                lambda cid=channel_id, wm=watermark: self._odoo.search_read(
                    "mail.message",
                    domain=[
                        ["res_id", "=", cid],
                        ["model", "=", "mail.channel"],
                        ["id", ">", wm],
                        ["message_type", "=", "comment"],
                        ["author_id.name", "not ilike", BOT_AUTHOR_PREFIX]
                    ],
                    fields=["id", "body", "author_id", "date", "partner_ids"],
                    limit=10
                )
            )

            for msg in messages:
                msg_id = msg["id"]
                if msg_id in self._processed_msg_ids:
                    continue
                self._processed_msg_ids.add(msg_id)
                self._channel_watermarks[channel_id] = max(
                    self._channel_watermarks.get(channel_id, 0),
                    msg_id
                )

                # Lấy partner_id của người gửi (dùng làm user_id)
                author = msg.get("author_id", [0, "Unknown"])
                partner_id = str(author[0]) if isinstance(author, list) else "0"
                author_name = author[1] if isinstance(author, list) else "Unknown"

                # Làm sạch HTML body
                body = self._strip_html(msg.get("body", ""))
                if not body or len(body) < 2:
                    continue

                print(f"   💬 [LIVECHAT] Channel {channel_id} | {author_name}: {body[:50]}")

                channel_msg = ChannelMessage(
                    channel="livechat",
                    user_id=str(channel_id),  # Dùng channel_id để gửi reply
                    text=body,
                    raw=msg,
                    metadata={
                        "channel_id": channel_id,
                        "partner_id": partner_id,
                        "author_name": author_name,
                        "msg_id": msg_id
                    }
                )

                try:
                    response = await message_handler(channel_msg)
                    if response:
                        await self.send_message(str(channel_id), response)
                except Exception as ex:
                    print(f"   ❌ [LIVECHAT HANDLER]: {ex}")
                    await self.send_message(
                        str(channel_id),
                        "❌ Xin lỗi, tôi đang gặp sự cố. Vui lòng thử lại!"
                    )

        # Giới hạn processed_msg_ids để tránh memory leak
        if len(self._processed_msg_ids) > 10000:
            # Giữ lại 5000 IDs mới nhất
            sorted_ids = sorted(self._processed_msg_ids)
            self._processed_msg_ids = set(sorted_ids[-5000:])

    @staticmethod
    def _strip_html(html: str) -> str:
        """Loại bỏ HTML tags khỏi Odoo message body."""
        import re
        clean = re.sub(r"<[^>]+>", "", html)
        return clean.strip()
