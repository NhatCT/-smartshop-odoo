"""
Conversation Memory Service — SmartShop Odoo 19
Quản lý bộ nhớ hội thoại đa lượt (Multi-turn Context Memory) theo user_id.
Sử dụng cờ Sliding Window (10 tin nhắn gần nhất) để giúp Claude Haiku nhớ ngữ cảnh chat trước đó.
"""

from __future__ import annotations

import time


class ConversationMemoryService:
    """
    In-memory Conversation History Store với Sliding Window & TTL Expiration.
    """
    def __init__(self, max_messages: int = 10, ttl_seconds: int = 3600) -> None:
        self._store: dict[str, list[dict]] = {}
        self._last_active: dict[str, float] = {}
        self.max_messages = max_messages
        self.ttl_seconds = ttl_seconds

    def get_history(self, user_id: str) -> list[dict]:
        """Lấy danh sách tin nhắn lịch sử của user_id với cờ tự động xóa TTL."""
        now = time.time()
        last_time = self._last_active.get(user_id, 0)

        # Quá TTL -> Tự động xóa bộ nhớ cũ (Auto Clear)
        if last_time > 0 and (now - last_time > self.ttl_seconds):
            self._store[user_id] = []

        return list(self._store.get(user_id, []))

    def add_user_message(self, user_id: str, content: str) -> None:
        """Thêm tin nhắn người dùng vào bộ nhớ."""
        history = self.get_history(user_id)
        history.append({"role": "user", "content": content})
        self._trim_and_save(user_id, history)

    def add_assistant_message(self, user_id: str, content: str) -> None:
        """Thêm phản hồi của assistant vào bộ nhớ."""
        history = self.get_history(user_id)
        history.append({"role": "assistant", "content": content})
        self._trim_and_save(user_id, history)

    def clear_history(self, user_id: str) -> None:
        """Xóa bộ nhớ hội thoại của user (lệnh /clear hoặc /reset)."""
        self._store[user_id] = []
        self._last_active[user_id] = time.time()

    def _trim_and_save(self, user_id: str, history: list[dict]) -> None:
        """Cắt bớt lịch sử theo sliding window để tránh phình token."""
        clean_history = []
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                clean_history.append({"role": role, "content": content})

        if len(clean_history) > self.max_messages:
            clean_history = clean_history[-self.max_messages:]

        self._store[user_id] = clean_history
        self._last_active[user_id] = time.time()
