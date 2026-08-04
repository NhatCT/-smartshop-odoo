"""
Model Router — SmartShop Odoo 19 AI Gateway (Layer 5)
Chuyển đổi linh hoạt model dựa trên môi trường và chỉ thị của Lead (mặc định Claude Haiku).
Tối ưu tối đa chi phí API và Tốc độ phản hồi.
"""

import os


class ModelRouter:
    """
    Tầng 5: Dynamic Model Router.
    Phù hợp với chỉ thị bắt buộc dùng Claude Haiku từ Team Lead.
    """
    def select_model(self, intent: str) -> str:
        # 1. Nếu chỉ định cố định CLAUDE_MODEL trong .env -> Dùng ngay
        default_model = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

        # 2. Chỉ dùng Sonnet nếu được khai báo tường minh trong .env (CLAUDE_SONNET_MODEL)
        if intent in ("SALE_ORDER_CREATE", "ANALYTICS_REPORT"):
            sonnet_env = os.getenv("CLAUDE_SONNET_MODEL")
            if sonnet_env:
                return sonnet_env

        # 3. Mặc định dùng Claude Haiku theo chỉ thị của Lead (Nhanh, Rẻ, Hoạt động 100%)
        return default_model
