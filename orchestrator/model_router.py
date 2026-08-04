"""
Model Router — SmartShop Odoo 19 AI Gateway (Layer 5)
Chuyển đổi linh hoạt giữa Claude Haiku (Tác vụ đơn giản/Tra cứu) và Claude Sonnet (Tác vụ tạo đơn/Mơ hồ).
Tối ưu tối đa chi phí API và Tốc độ phản hồi.
"""

import os


class ModelRouter:
    """
    Tầng 5: Dynamic Model Router.
    """
    def select_model(self, intent: str) -> str:
        # Nếu cấu hình cố định model qua biến môi trường CLAUDE_MODEL -> Ưu tiên dùng
        forced_model = os.getenv("CLAUDE_MODEL")
        if forced_model:
            return forced_model

        # Tác vụ phức tạp cần suy luận nhiều bước -> Dùng Sonnet
        if intent in ("SALE_ORDER_CREATE", "ANALYTICS_REPORT"):
            return os.getenv("CLAUDE_SONNET_MODEL", "claude-3-5-sonnet-20241022")

        # Tác vụ tra cứu đơn giản -> Dùng Haiku (Nhanh & Rẻ)
        return os.getenv("CLAUDE_HAIKU_MODEL", "claude-haiku-4-5-20251001")
