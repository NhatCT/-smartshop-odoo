"""
Idempotency Guard — Tầng 2: API Gateway
Chống xử lý trùng lặp request (Request Deduplication).
Window: 5 phút. Key: hash(user_id + message_text).
"""

import time
import hashlib
import threading
from collections import OrderedDict


class IdempotencyGuard:
    """
    Request Deduplication với TTL window 5 phút.
    Nếu cùng user gửi cùng nội dung trong 5 phút → trả cached response, không xử lý lại.
    """

    def __init__(self, ttl_seconds: int = 300, max_cache_size: int = 10000):
        self._ttl = ttl_seconds
        self._max_size = max_cache_size
        # {key: {"response": str, "timestamp": float}}
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def _make_key(self, user_id: str, message: str) -> str:
        """Tạo idempotency key từ user_id + message hash."""
        raw = f"{user_id}:{message.strip().lower()[:200]}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def check(self, user_id: str, message: str) -> tuple[bool, str | None]:
        """
        Kiểm tra request có phải duplicate không.
        Returns: (is_duplicate: bool, cached_response: str | None)
        """
        key = self._make_key(user_id, message)
        now = time.time()

        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if now - entry["timestamp"] < self._ttl:
                    # Cache hit — trả cached response
                    self._cache.move_to_end(key)
                    return True, entry["response"]
                else:
                    # Expired — xóa
                    del self._cache[key]

        return False, None

    def store(self, user_id: str, message: str, response: str) -> None:
        """Lưu response vào cache sau khi xử lý xong."""
        key = self._make_key(user_id, message)
        now = time.time()

        with self._lock:
            # Evict oldest nếu cache đầy
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            self._cache[key] = {
                "response": response,
                "timestamp": now
            }
            self._cache.move_to_end(key)

    def invalidate(self, user_id: str, message: str) -> None:
        """Xóa cache entry (dùng khi cần force re-process)."""
        key = self._make_key(user_id, message)
        with self._lock:
            self._cache.pop(key, None)

    def cleanup_expired(self) -> int:
        """Dọn dẹp expired entries. Returns số entries đã xóa."""
        now = time.time()
        expired_keys = []
        with self._lock:
            for key, entry in self._cache.items():
                if now - entry["timestamp"] >= self._ttl:
                    expired_keys.append(key)
            for key in expired_keys:
                del self._cache[key]
        return len(expired_keys)


# Singleton instance — không dedup lệnh /register /verify (chỉ dedup AI queries)
_idempotency_guard = IdempotencyGuard(ttl_seconds=300)

SKIP_DEDUP_PREFIXES = {"/register", "/verify", "/clear", "/reset", "/my_role", "/start"}


def get_idempotency_guard() -> IdempotencyGuard:
    return _idempotency_guard


def should_dedup(message: str) -> bool:
    """Kiểm tra xem message có cần dedup không (bỏ qua các lệnh hệ thống)."""
    msg = message.strip().lower()
    return not any(msg.startswith(prefix) for prefix in SKIP_DEDUP_PREFIXES)
