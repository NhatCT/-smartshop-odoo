"""
Smart Entity Resolver — SmartShop Odoo 19 AI Gateway
Tiền xử lý (Pre-processing) tra cứu Khách hàng (partner.lookup), Đơn hàng (order.lookup), và Sản phẩm (product.search)
trực tiếp qua Odoo RPC. Đảm bảo phân tách rõ ràng giữa "tìm ai" và "tìm cái gì".
"""

from data_layer.connectors.odoo_rpc import OdooClient


class SmartEntityResolver:
    """
    Bộ phân giải Thực thể ERP Thông minh với 3 Tool Resolver riêng biệt:
    1. partner.lookup — Tìm Khách hàng
    2. order.lookup   — Tìm Đơn hàng (Sale Order) theo Partner ID / Tên đơn S0001
    3. product.search — Tìm Sản phẩm / SKU
    """
    def __init__(self, odoo_client: OdooClient | None = None):
        self.odoo_client = odoo_client or OdooClient()

    def resolve_partner(self, query: str | int) -> dict | None:
        """partner.lookup: Tra cứu Khách hàng từ ID, Tên, Ref, Email, SĐT."""
        if not query:
            return None

        q_str = str(query).strip()

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

    def resolve_sale_order(self, partner_id: int | None = None, order_query: str | None = None) -> list[dict]:
        """
        order.lookup: Tách biệt tra cứu Đơn hàng khỏi Khách hàng.
        Giải quyết câu hỏi kiểu: "Đơn của Alice ở đâu?" (partner.lookup Alice -> partner_id=5 -> order.lookup partner_id=5).
        """
        domain = []
        if partner_id:
            domain.append(["partner_id", "=", partner_id])
        if order_query:
            domain.append(["name", "ilike", str(order_query).strip()])

        if not domain:
            return []

        try:
            return self.odoo_client.search_read(
                model="sale.order",
                domain=domain,
                fields=["id", "name", "partner_id", "amount_total", "state", "date_order"],
                limit=5
            )
        except Exception as e:
            print(f"⚠️ [SmartEntityResolver] Lỗi query order.lookup: {e}")
            return []

    def resolve_product(self, query: str | int) -> dict | None:
        """product.search: Tra cứu Sản phẩm từ ID, Tên hoặc SKU."""
        if not query:
            return None

        q_str = str(query).strip()

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
