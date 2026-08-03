"""
SmartShop AI Gateway — Tầng Bảo mật & Phân quyền
Layer 2: API Gateway (Auth + Rate Limit + Idempotency + Request Dedup)
"""
from .auth import SecurityGateway
from .rate_limiter import RateLimiter, get_rate_limiter
from .idempotency import IdempotencyGuard, get_idempotency_guard

__all__ = ["SecurityGateway", "RateLimiter", "get_rate_limiter", "IdempotencyGuard", "get_idempotency_guard"]
