"""
Order Draft State Service — SmartShop Odoo 19 AI Gateway
Quản lý Trạng thái Đơn nháp (Draft Order State Machine).
"""

import time
from dataclasses import dataclass, field


@dataclass
class DraftOrderItem:
    product_id: int
    name: str
    qty: float = 1.0
    unit_price: float = 0.0
    discount: float = 0.0  # % chiết khấu (0-100)

    @property
    def subtotal(self) -> float:
        """Thành tiền sau chiết khấu."""
        return self.qty * self.unit_price * (1 - self.discount / 100)


@dataclass
class DraftOrder:
    user_id: str
    customer_id: int | None = None
    customer_name: str | None = None
    items: list[DraftOrderItem] = field(default_factory=list)
    status: str = "BUILDING"   # BUILDING -> READY -> SUBMITTED
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    @property
    def total_amount(self) -> float:
        return sum(item.subtotal for item in self.items)

    def is_complete(self) -> bool:
        return self.customer_id is not None and len(self.items) > 0

    def format_summary(self) -> str:
        """Xuất bản tóm tắt đơn nháp theo Markdown."""
        cust_str = f"**{self.customer_name}** (ID: {self.customer_id})" if self.customer_id else "❌ _Chưa chọn_"

        if not self.items:
            items_str = "_Chưa có sản phẩm nào_"
        else:
            lines = []
            for i, item in enumerate(self.items, 1):
                price_fmt = f"{item.unit_price:,.0f} VNĐ" if item.unit_price else "Theo giá niêm yết Odoo"
                lines.append(f"{i}. **{item.name}** x{item.qty:g} ({price_fmt})")
            items_str = "\n".join(lines)

        total_str = f"**{self.total_amount:,.0f} VNĐ**" if self.total_amount > 0 else "_Tự động tính trên Odoo_"

        return (
            f"🛒 **ĐƠN HÀNG NHÁP HỆ THỐNG**\n"
            f"• **Khách hàng**: {cust_str}\n"
            f"• **Danh sách sản phẩm**:\n{items_str}\n"
            f"• **Tổng tạm tính**: {total_str}"
        )


class OrderDraftStateService:
    """
    State Store quản lý các Đơn nháp đang khởi tạo của Người dùng.
    """
    def __init__(self, ttl_seconds: int = 1800):
        self._store: dict[str, DraftOrder] = {}
        self.ttl_seconds = ttl_seconds

    def get_draft(self, user_id: str) -> DraftOrder:
        """Lấy đơn nháp hiện tại của user_id (nếu chưa quá TTL)."""
        now = time.time()
        draft = self._store.get(user_id)

        if draft and (now - draft.last_updated > self.ttl_seconds):
            self.clear_draft(user_id)
            draft = None

        if not draft:
            draft = DraftOrder(user_id=user_id)
            self._store[user_id] = draft

        return draft

    def set_customer(self, user_id: str, partner_id: int, partner_name: str) -> DraftOrder:
        """Cập nhật thông tin khách hàng cho đơn nháp."""
        draft = self.get_draft(user_id)
        draft.customer_id = partner_id
        draft.customer_name = partner_name
        draft.last_updated = time.time()
        return draft

    def add_item(self, user_id: str, product_id: int, product_name: str, qty: float = 1.0, unit_price: float = 0.0) -> DraftOrder:
        """Thêm hoặc cộng dồn số lượng sản phẩm vào đơn nháp."""
        draft = self.get_draft(user_id)

        existing = next((item for item in draft.items if item.product_id == product_id), None)
        if existing:
            existing.qty += qty
            if unit_price > 0:
                existing.unit_price = unit_price
        else:
            draft.items.append(DraftOrderItem(
                product_id=product_id,
                name=product_name,
                qty=qty,
                unit_price=unit_price
            ))

        draft.last_updated = time.time()
        return draft

    def set_discount(self, user_id: str, product_id: int, discount_pct: float) -> DraftOrder:
        """Áp dụng chiết khấu (%) cho một sản phẩm trong đơn nháp."""
        draft = self.get_draft(user_id)
        item = next((i for i in draft.items if i.product_id == product_id), None)
        if item:
            item.discount = max(0.0, min(100.0, float(discount_pct)))
            draft.last_updated = time.time()
        return draft

    def clear_draft(self, user_id: str):
        """Xóa bỏ đơn nháp hiện tại của user."""
        if user_id in self._store:
            del self._store[user_id]
