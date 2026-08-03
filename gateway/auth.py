"""
Gateway Auth — Tầng 2: API Gateway
Thin wrapper re-export SecurityGateway từ auth_gateway.py gốc.
Giữ backward compatibility — auth_gateway.py vẫn là source of truth.
"""

# Re-export để import chuẩn qua gateway package
from auth_gateway import SecurityGateway, ROLE_TOOLS_MAP, PREDEFINED_EMAIL_ROLES

__all__ = ["SecurityGateway", "ROLE_TOOLS_MAP", "PREDEFINED_EMAIL_ROLES"]
