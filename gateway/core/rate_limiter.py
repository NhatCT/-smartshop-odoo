import time
import asyncio
from collections import defaultdict

class RateLimiter:
    def __init__(self, limit=30, window=60):
        self.limit = limit
        self.window = window
        self._requests = defaultdict(list)
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: str) -> bool:
        now = time.time()
        async with self._lock:
            timestamps = self._requests[user_id]
            valid_timestamps = [ts for ts in timestamps if now - ts < self.window]
            self._requests[user_id] = valid_timestamps
            if len(valid_timestamps) >= self.limit:
                return False
            self._requests[user_id].append(now)
            return True

_global_rate_limiter = None
def get_rate_limiter(limit=30, window=60):
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(limit, window)
    return _global_rate_limiter
