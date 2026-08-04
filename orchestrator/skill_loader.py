"""
Skill Loader — SmartShop Odoo 19 AI Gateway (Layer 3)
Chỉ nạp đúng tập Tool liên quan trực tiếp đến Intent đã phân loại và Quyền Odoo của User.
Tránh nhét toàn bộ 20 tool làm bối rối AI và lãng phí token.
"""


class SkillLoader:
    """
    Tầng 3: Dynamic Skill & Tool Loader.
    """
    INTENT_TOOL_MAP = {
        "INVENTORY_LOOKUP": {"get_stock_quant", "search_records", "list_products"},
        "PRODUCT_SEARCH": {"search_records", "list_products"},
        "ORDER_LOOKUP": {"get_sale_order", "search_records", "list_products"},
        "SALE_ORDER_CREATE": {"create_sale_order", "search_records", "get_sale_order", "list_products"},
        "PARTNER_LOOKUP": {"search_records"},
        "ANALYTICS_REPORT": {"aggregate_records", "search_records"},
        "GENERAL": {"search_records", "list_products"}
    }

    def get_effective_tools(self, intent: str, user_allowed_tools: list[str]) -> set[str]:
        """
        Giao của (Tools theo Intent) và (Tools được phép theo User Role Odoo).
        """
        intent_tools = self.INTENT_TOOL_MAP.get(intent, {"search_records", "list_products"})
        user_tools = set(user_allowed_tools) if user_allowed_tools else intent_tools

        # Retain only tools permitted by BOTH intent and user role
        return intent_tools.intersection(user_tools)
