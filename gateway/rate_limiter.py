"""
Rate Limiter — Tầng 2: API Gateway
Giới hạn 30 requests/phút/user (sliding window in-memory).
Thiết kế Redis-ready: thay _store bằng Redis client là xong.
"""

import time
import threading
from collections import defaultdict, deque


class RateLimiter:
    """
    Sliding Window Rate Limiter (in-memory, thread-safe).
    Mặc định: 30 req/phút/user.
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self._max_requests = max_requests
        self._window = window_seconds
        self._store: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, user_id: str) -> tuple[bool, dict]:
        """
        Kiểm tra xem user có vượt giới hạn không.
        Returns: (allowed: bool, info: dict)
        """
        now = time.time()
        key = str(user_id)

        with self._lock:
            window = self._store[key]

            # Loại bỏ timestamps đã hết window
            while window and window[0] < now - self._window:
                window.popleft()

            current_count = len(window)

            if current_count >= self._max_requests:
                oldest = window[0] if window else now
                retry_after = int(self._window - (now - oldest)) + 1
                return False, {
                    "allowed": False,
                    "current": current_count,
                    "limit": self._max_requests,
                    "retry_after_seconds": retry_after,
                    "message": (
                        f"⚠️ Bạn đã gửi quá {self._max_requests} tin nhắn/phút.\n"
                        f"Vui lòng đợi {retry_after} giây rồi thử lại."
                    )
                }

            window.append(now)
            return True, {
                "allowed": True,
                "current": current_count + 1,
                "limit": self._max_requests,
                "remaining": self._max_requests - current_count - 1
            }

    def reset(self, user_id: str) -> None:
        """Reset counter cho user (dùng khi test hoặc admin override)."""
        with self._lock:
            self._store.pop(str(user_id), None)

    def get_stats(self, user_id: str) -> dict:
        """Lấy thống kê sử dụng của user."""
        now = time.time()
        key = str(user_id)
        with self._lock:
            window = self._store.get(key, deque())
            active = [t for t in window if t >= now - self._window]
            return {
                "user_id": key,
                "requests_in_window": len(active),
                "limit": self._max_requests,
                "window_seconds": self._window,
                "remaining": max(0, self._max_requests - len(active))
            }


# Singleton instance dùng chung toàn app
_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)


def get_rate_limiter() -> RateLimiter:
    """Lấy singleton RateLimiter instance."""
    return _rate_limiter
