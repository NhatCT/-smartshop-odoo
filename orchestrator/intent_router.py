"""
Intent Router — SmartShop Odoo 19 AI Gateway (Layer 1)
Phân loại ý định từ câu chat tiếng Việt thành 6 nhóm Intent chính:
- INVENTORY_LOOKUP: Tra cứu tồn kho, vị trí kho.
- PRODUCT_SEARCH: Tìm sản phẩm, giá bán, SKU.
- ORDER_LOOKUP: Tra cứu đơn hàng, trạng thái đơn, đơn nháp.
- SALE_ORDER_CREATE: Báo giá nháp, tạo đơn hàng.
- PARTNER_LOOKUP: Tra cứu thông tin khách hàng.
- ANALYTICS_REPORT: Báo cáo doanh số, tài chính.
"""


class IntentRouter:
    """
    Tầng 1: Phân loại Ý định (Intent Classification Engine).
    Sử dụng regex & keyword matching tốc độ cực nhanh (< 1ms) không tốn API token.
    """
    def route_intent(self, text: str) -> str:
        text_lower = text.lower().strip()

        # 1. Báo cáo doanh số / tài chính
        if any(kw in text_lower for kw in ["báo cáo", "doanh số", "tài chính", "doanh thu", "lợi nhuận", "tổng quan"]):
            return "ANALYTICS_REPORT"

        # 2. Tra cứu đơn hàng (Phân biệt với Tạo đơn hàng)
        if any(kw in text_lower for kw in ["tra cứu đơn", "xem đơn", "đơn hàng", "đơn nháp", "trạng thái đơn", "đơn của", "sale order", "order"]):
            if not any(kw in text_lower for kw in ["tạo đơn", "lên đơn", "đặt hàng"]):
                return "ORDER_LOOKUP"

        # 3. Tạo đơn / Báo giá (bao gồm chiết khấu/giảm giá — thường xuất hiện trong luồng tạo đơn)
        if any(kw in text_lower for kw in [
            "tạo đơn", "lên đơn", "báo giá", "bán hàng", "chốt đơn", "đặt hàng",
            "chiết khấu", "giảm giá", "discount", "khuyến mãi"
        ]):
            return "SALE_ORDER_CREATE"

        # 4. Tra cứu tồn kho
        if any(kw in text_lower for kw in ["tồn kho", "kiểm kho", "còn hàng", "hàng tồn", "kho", "stock"]):
            return "INVENTORY_LOOKUP"

        # 5. Tra cứu khách hàng
        if any(kw in text_lower for kw in ["khách hàng", "đối tác", "partner", "khách"]):
            return "PARTNER_LOOKUP"

        # 6. Tra cứu sản phẩm / Giá bán
        if any(kw in text_lower for kw in ["giá", "sản phẩm", "mặt hàng", "sku", "mã hàng", "iphone"]):
            return "PRODUCT_SEARCH"

        return "GENERAL"
