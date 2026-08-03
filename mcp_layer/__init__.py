"""
SmartShop AI Gateway — Tầng MCP (Model Context Protocol)
Layer 5: Odoo MCP với 30min TTL Cache + Fallback + Async Timeout
"""
from .mcp_cache import MCPCache
from .mcp_client import MCPClientWrapper

__all__ = ["MCPCache", "MCPClientWrapper"]
