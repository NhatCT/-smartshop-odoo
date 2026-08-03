import time
import asyncio

class IdempotencyGuard:
    def __init__(self, ttl_seconds=10):
        self.ttl_seconds = ttl_seconds
        self._processed = {}
        self._lock = asyncio.Lock()

    async def check_and_record(self, key: str) -> bool:
        now = time.time()
        async with self._lock:
            if key in self._processed:
                timestamp = self._processed[key]
                if now - timestamp < self.ttl_seconds:
                    return False
            self._processed[key] = now
            return True

_global_idempotency_guard = None
def get_idempotency_guard(ttl_seconds=10):
    global _global_idempotency_guard
    if _global_idempotency_guard is None:
        _global_idempotency_guard = IdempotencyGuard(ttl_seconds)
    return _global_idempotency_guard
