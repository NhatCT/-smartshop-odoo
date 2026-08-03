"""
Validation Agent — Tầng 3: Workflow Agents
Skill: Kiểm tra độ chính xác, phát hiện đơn hàng cần HITL phê duyệt.
Pipeline position: SECOND (Recommendation → Validation → Fulfillment)

Quy tắc HITL (Human-in-the-Loop):
- Đơn hàng > 20.000.000 VNĐ → cần Anthony phê duyệt
- Chiết khấu > 15% → cần Anthony phê duyệt
- Sản phẩm không tồn tại trong Odoo → từ chối, gợi ý sản phẩm gần đúng
"""

from __future__ import annotations
from typing import Any
import os

from .base_agent import BaseAgent, AgentResult
from gateway.auth import SecurityGateway, generate_approval_token

# Ngưỡng HITL
HIGH_VALUE_THRESHOLD_VND = 20_000_000
HIGH_DISCOUNT_THRESHOLD_PCT = 15.0

# Telegram ID người phê duyệt (Anthony)
APPROVER_TELEGRAM_ID = os.getenv("APPROVER_TELEGRAM_ID", "6553206564")


class ValidationAgent(BaseAgent):
    """
    Validation Agent: Kiểm tra business rules và HITL gates.
    Nếu vượt ngưỡng → set needs_approval=True, không tự chốt đơn.
    """

    def __init__(self):
        super().__init__(name="validation")
        self._gateway = SecurityGateway()

    async def run(
        self,
        user_id: str,
        user_text: str,
        user_info: dict,
        mcp_session: Any,
        context: dict | None = None,
    ) -> AgentResult:
        context = context or {}
        order_amount = context.get("order_amount_vnd", 0)
        discount_pct = context.get("discount_pct", 0.0)
        order_name = context.get("order_name", "")
        role = user_info.get("official_role", "viewer")

        # --- Rule 1: Chỉ sales_manager & sales_staff được tạo đơn ---
        if role not in ("sales_manager", "sales_staff"):
            return AgentResult(
                success=False,
                response=(
                    f"⛔ Vai trò **{role.upper()}** không có quyền tạo đơn hàng.\n"
                    f"Chỉ Sales Manager và Sales Staff mới được phép thực hiện thao tác này."
                ),
                metadata={"validation_failed": True, "reason": "insufficient_role"}
            )

        # --- Rule 2: High-Value Order → HITL ---
        needs_hitl, hitl_reason = self._gateway.check_high_value_order_approval(
            order_amount_vnd=order_amount,
            discount_percent=discount_pct
        )

        if needs_hitl:
            token = generate_approval_token(order_name, str(user_id))
            approval_context = {
                "order_name": order_name,
                "order_amount": order_amount,
                "discount_pct": discount_pct,
                "requester_id": str(user_id),
                "requester_name": user_info.get("user_info", {}).get("full_name", ""),
                "token": token,
                "approver_id": APPROVER_TELEGRAM_ID,
                "approve_callback": f"approve_{order_name}_{token}",
                "reject_callback": f"reject_{order_name}_{token}",
            }
            return AgentResult(
                success=True,
                response=hitl_reason,
                needs_approval=True,
                approval_context=approval_context,
                next_agent=None,  # Dừng pipeline — chờ Anthony
                metadata=context
            )

        # --- Validation passed → chuyển sang Fulfillment ---
        return AgentResult(
            success=True,
            response="✅ Đơn hàng hợp lệ. Đang xử lý...",
            needs_approval=False,
            next_agent="fulfillment",
            metadata={**context, "validation_passed": True}
        )

    def validate_product_query(self, query: str) -> tuple[bool, str]:
        """
        Kiểm tra query tìm sản phẩm có hợp lệ không.
        Returns: (valid: bool, message: str)
        """
        if not query or len(query.strip()) < 2:
            return False, "⚠️ Vui lòng nhập ít nhất 2 ký tự để tìm kiếm sản phẩm."
        if len(query) > 200:
            return False, "⚠️ Từ khóa tìm kiếm quá dài. Vui lòng rút ngắn."
        return True, ""

    def validate_order_lines(self, lines: list[dict]) -> tuple[bool, str]:
        """
        Kiểm tra danh sách sản phẩm trong đơn hàng.
        Returns: (valid: bool, error_message: str)
        """
        if not lines:
            return False, "❌ Đơn hàng không có sản phẩm nào."
        for i, line in enumerate(lines):
            if not line.get("product_id"):
                return False, f"❌ Dòng {i+1}: Thiếu thông tin sản phẩm."
            qty = line.get("product_uom_qty", 0)
            if qty <= 0:
                return False, f"❌ Dòng {i+1}: Số lượng phải lớn hơn 0."
        return True, ""
