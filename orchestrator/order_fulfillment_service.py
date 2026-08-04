"""Order Fulfillment Service — SmartShop Odoo 19 AI Gateway."""

from __future__ import annotations

from data_layer.connectors.odoo_rpc import OdooClient
from orchestrator.draft_order_service import OrderDraftStateService


class OrderFulfillmentService:
    """Chốt đơn sau khi Manager phê duyệt — tạo sale.order thực tế trên Odoo."""

    def __init__(self, draft_service=None, odoo_client=None):
        self.draft_service = draft_service or OrderDraftStateService(ttl_seconds=1800)
        self.odoo_client = odoo_client or OdooClient()
        self._order_refs: dict[str, str] = {}

    def register_order_reference(self, user_id: str, order_name: str) -> None:
        self._order_refs[order_name] = str(user_id)

    def approve_order(self, order_name: str, telegram_id: str | None = None):
        user_id = telegram_id or self._order_refs.get(order_name)
        if not user_id:
            return False, f"❌ Không tìm thấy đơn nháp ứng với `{order_name}`."
        draft = self.draft_service.get_draft(user_id)
        if draft.status == "SUBMITTED":
            return False, f"⚠️ Đơn `{order_name}` đã được xử lý trước đó."
        ok, msg = self._create_sale_order(draft, order_name)
        if ok:
            draft.status = "SUBMITTED"
            self.draft_service.clear_draft(user_id)
            self._order_refs.pop(order_name, None)
        return ok, msg

    def reject_order(self, order_name: str, telegram_id: str | None = None):
        user_id = telegram_id or self._order_refs.get(order_name)
        if not user_id:
            return False, f"❌ Không tìm thấy đơn nháp ứng với `{order_name}`."
        self.draft_service.clear_draft(user_id)
        self._order_refs.pop(order_name, None)
        return True, f"✅ Đơn `{order_name}` đã bị từ chối. Nhân viên sẽ được thông báo."

    def _create_sale_order(self, draft, order_name: str):
        if not draft.customer_id or not draft.items:
            return False, f"❌ Đơn nháp `{order_name}` thiếu khách hàng hoặc sản phẩm."
        order_lines = [
            (0, 0, {
                "product_id": item.product_id,
                "name": item.name,
                "product_uom_qty": item.qty,
                "price_unit": item.unit_price or 0.0,
                "discount": item.discount or 0.0,
            })
            for item in draft.items
        ]
        try:
            order_id = self.odoo_client.create("sale.order", {
                "partner_id": draft.customer_id,
                "order_line": order_lines,
                "state": "draft",
            })
        except Exception as e:
            print(f"❌ [OrderFulfillment] Lỗi tạo sale.order `{order_name}`: {e}")
            return False, f"❌ Lỗi tạo Sale Order trên Odoo: {e}"
        return True, (
            f"✅ **{order_name}** đã được Manager PHÊ DUYỆT và tạo thành công trên Odoo "
            f"(Sale Order ID: {order_id})."
        )