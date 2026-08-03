"""
Enterprise Self-Describing Prompt Engine — SmartShop Odoo 19 AI Gateway
Zero Role Matrix: Claude tự suy luận quyền hạn trực tiếp từ native Odoo groups.
"""

from gateway.services.config_registry_service import ConfigRegistryService

_config_registry = None
def _get_registry():
    global _config_registry
    if _config_registry is None:
        _config_registry = ConfigRegistryService()
    return _config_registry


DEFAULT_BASE_PROMPT = """\
Bạn là Trợ lý AI Điều hành của Doanh nghiệp Odoo 19.
Nhiệm vụ: Hỗ trợ người dùng tra cứu thông tin, quản lý nghiệp vụ và thực thi quy trình nội bộ.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NGƯỜI DÙNG ĐÃ XÁC THỰC (Odoo SaaS Live):
  Họ và Tên : {full_name}
  Email Odoo : {email}
  Nhóm quyền: (Lấy trực tiếp từ Odoo Access Rights — nguồn sự thật duy nhất)
{groups_block}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NGUYÊN TẮC PHÂN QUYỀN (ZERO-TRUST — KHÔNG ĐƯỢC VI PHẠM):
Dựa vào danh sách nhóm quyền Odoo ở trên, hãy TỰ XÁC ĐỊNH quyền hạn của người dùng:
- Nhóm "Bán hàng / Quản trị viên" hoặc "Vai trò / Quản trị viên" → Toàn quyền: xem báo cáo doanh số, tạo & duyệt đơn.
- Nhóm "Bán hàng / Người dùng" → Được tư vấn sản phẩm, tạo đơn hàng nhỏ. Không xem báo cáo tài chính tổng quan.
- Nhóm "Tồn kho / Người dùng" → Chỉ kiểm kho và tra cứu sản phẩm. Không xem doanh số, không tạo đơn.
- Nhóm "Kế toán / ..." → Được xem hóa đơn, báo cáo tài chính. Không tạo Sale Order.
- Không có nhóm nghiệp vụ nào → Chỉ tra cứu thông tin công khai.

⛔ NẾU USER YÊU CẦU VƯỢT QUYỀN: Tuyệt đối không gọi Tool. Phản hồi từ chối ngay lập tức, nêu rõ nhóm quyền bị thiếu.

QUY TRÌNH THỰC THI (KHI ĐỦ QUYỀN):
1. TRUY VẤN DỮ LIỆU: Gọi MCP Tool (search_records, aggregate_records) để lấy dữ liệu thực tế từ Odoo.
2. TRÌNH BÀY: Kết quả dưới dạng bảng Markdown sạch, rõ ràng, có tổng hợp.
3. ĐƠN HÀNG LỚN (>= {approval_threshold}):
   - Không tạo trực tiếp. Thông báo cho user cần phê duyệt từ Quản lý.
   - Gửi về cuối câu trả lời: `[NEED_APPROVAL] {{"order_name": "...", "total": <số tiền>}}`
4. KHI ĐÃ DUYỆT: Nhận "[MANAGER_APPROVED] Tạo đơn đi" → Dùng Tool tạo Sale Order.
"""


def build_system_prompt(user_info: dict, role: str = "") -> str:
    """
    Sinh System Prompt động từ raw Odoo groups — không có role matrix trong code.
    Claude tự suy luận quyền hạn từ danh sách nhóm quyền Odoo thực tế.
    """
    registry = _get_registry()

    full_name = user_info.get("full_name", "Khách hàng")
    email = user_info.get("email", "unknown")
    groups = user_info.get("odoo_groups", [])

    # Định dạng danh sách nhóm quyền dễ đọc
    if groups:
        # Lọc bỏ các nhóm kỹ thuật nội bộ không liên quan đến nghiệp vụ
        skip_keywords = ["Technical", "B qua", "Địa chỉ", "Trình chỉnh", "Trang web"]
        filtered = [g for g in groups if not any(kw in g for kw in skip_keywords)]
        groups_block = "\n".join(f"    • {g}" for g in filtered) if filtered else "    • (Không có nhóm nghiệp vụ)"
    else:
        groups_block = "    • (Không thể đọc nhóm quyền — hãy thận trọng)"

    # Đọc ngưỡng phê duyệt đơn hàng từ Odoo System Parameter
    try:
        thresh_val = float(registry.get_parameter("smartshop.approval_threshold", "20000000"))
    except Exception:
        thresh_val = 20_000_000
    thresh_str = f"{thresh_val:,.0f} VNĐ"

    # Đọc Custom Base Prompt từ Odoo System Parameter (Admin có thể tùy chỉnh)
    try:
        custom = registry.get_parameter("smartshop.ai_system_prompt")
        base_template = custom if custom else DEFAULT_BASE_PROMPT
    except Exception:
        base_template = DEFAULT_BASE_PROMPT

    try:
        return base_template.format(
            full_name=full_name,
            email=email,
            groups_block=groups_block,
            approval_threshold=thresh_str,
        )
    except Exception:
        # Fallback nếu custom template thiếu placeholder
        return (
            DEFAULT_BASE_PROMPT.format(
                full_name=full_name,
                email=email,
                groups_block=groups_block,
                approval_threshold=thresh_str,
            )
        )
