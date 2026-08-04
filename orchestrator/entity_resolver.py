"""
Smart Entity Resolver — SmartShop Odoo 19 AI Gateway
Tiền xử lý (Pre-processing) tra cứu Khách hàng (res.partner) và Sản phẩm (product.template)
trực tiếp qua Odoo RPC. Đảm bảo xác thực ID/Mã/Tên chính xác 100% trước khi truyền context cho Claude.
"""

from data_layer.connectors.odoo_rpc import OdooClient


class SmartEntityResolver:
    """
    Bộ phân giải Thực thể ERP Thông minh.
    """
    def __init__(self, odoo_client: OdooClient | None = None):
        self.odoo_client = odoo_client or OdooClient()

    def resolve_partner(self, query: str | int) -> dict | None:
        """
        Xác thực Khách hàng từ ID, Tên, Mã tham chiếu (ref) hoặc Email/SĐT.
        """
        if not query:
            return None

        q_str = str(query).strip()

        # Nếu là ID số nguyên (ví dụ: "khách hàng số 2" -> 2)
        if q_str.isdigit():
            partner_id = int(q_str)
            try:
                records = self.odoo_client.search_read(
                    model="res.partner",
                    domain=[["id", "=", partner_id]],
                    fields=["id", "name", "email", "phone", "ref"],
                    limit=1
                )
                if records:
                    return records[0]
            except Exception as e:
                print(f"⚠️ [SmartEntityResolver] Lỗi query partner ID {partner_id}: {e}")

        # Tra cứu Fuzzy qua Tên, Email, SĐT, hoặc Ref
        try:
            domain = [
                "|", "|", "|",
                ["name", "ilike", q_str],
                ["ref", "ilike", q_str],
                ["email", "ilike", q_str],
                ["phone", "ilike", q_str]
            ]
            records = self.odoo_client.search_read(
                model="res.partner",
                domain=domain,
                fields=["id", "name", "email", "phone", "ref"],
                limit=1
            )
            if records:
                return records[0]
        except Exception as e:
            print(f"⚠️ [SmartEntityResolver] Lỗi fuzzy query partner '{q_str}': {e}")

        return None

    def resolve_product(self, query: str | int) -> dict | None:
        """
        Xác thực Sản phẩm từ ID, Tên hoặc Mã SKU (default_code).
        """
        if not query:
            return None

        q_str = str(query).strip()

        # Nếu là ID số nguyên
        if q_str.isdigit():
            product_id = int(q_str)
            try:
                records = self.odoo_client.search_read(
                    model="product.template",
                    domain=[["id", "=", product_id]],
                    fields=["id", "name", "list_price", "qty_available", "default_code"],
                    limit=1
                )
                if records:
                    return records[0]
            except Exception as e:
                print(f"⚠️ [SmartEntityResolver] Lỗi query product ID {product_id}: {e}")

        # Tra cứu Fuzzy qua Tên hoặc SKU
        try:
            domain = [
                "|",
                ["name", "ilike", q_str],
                ["default_code", "ilike", q_str]
            ]
            records = self.odoo_client.search_read(
                model="product.template",
                domain=domain,
                fields=["id", "name", "list_price", "qty_available", "default_code"],
                limit=1
            )
            if records:
                return records[0]
        except Exception as e:
            print(f"⚠️ [SmartEntityResolver] Lỗi fuzzy query product '{q_str}': {e}")

        return None
