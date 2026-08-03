---
name: odoo-management
description: Quản lý, kiểm thử và tích hợp Odoo Smartshop MCP Server với Claude Desktop và OdooRPC.
---

# Odoo Management & MCP Integration Skill

Skill này cung cấp các hướng dẫn chi tiết để kiểm thử, quản lý và tích hợp Odoo Smartshop MCP Server với Claude Desktop theo đúng Quy tắc vàng #1 (**Do Not Reinvent The Wheel**).

## Kiến trúc hệ thống MCP
- **MCP Client (Agent & UI)**: Claude Desktop (tự động hóa Planning, ReAct Reasoning, Native Tool Calling & Render UI).
- **MCP Server**: Official `erpipe-org/mcp-odoo` (gói PyPI `odoo-mcp` v1.3.0+, 41 tools built-in, quản lý log stdio chuẩn, hỗ trợ `ODOO_MCP_ENABLE_WRITES=1`).
- **Odoo Instance**: Odoo SaaS (`smartshop-odoo.odoo.com`) tương tác qua XML-RPC / JSON-2 với Odoo User API Key bảo mật.

## Các lệnh chính (Quick Commands)

### 1. Kiểm tra sức khỏe toàn bộ hệ thống (System Audit)
Xác minh credentials `.env` (API Key) và kết nối Odoo:
```bash
python audit_system.py
```

### 2. Kiểm thử MCP Server trực tiếp
Khởi chạy thử MCP Server chính thức:
```bash
python -m odoo_mcp --help
python -m odoo_mcp --health
```

---

## 🛡️ Cấu hình Custom Instructions Chuẩn BI Analyst & Bảo Mật Phê Duyệt (Human-in-the-Loop)

Copy toàn bộ đoạn sau vào mục **Settings -> Custom Instructions** trên Claude Desktop:

```markdown
Bạn là Chuyên gia Phân tích Dữ liệu Kinh doanh (BI Analyst) cho hệ thống Odoo Smartshop.

Khi tương tác với người dùng qua MCP Tools của Odoo, hãy tuân thủ nghiêm ngặt các quy tắc sau:

1. QUY TẮC AN TOÀN BẢO MẬT DỮ LIỆU (WRITE APPROVAL RULE - QUAN TRỌNG NHẤT):
   - ĐỐI VỚI THAO TÁC ĐỌC (Search/Read): Tự động thực hiện ngay và trả về báo cáo.
   - ĐỐI VỚI MỌI THAO TÁC GHI (Tạo mới, Chỉnh sửa, Xóa, Xác nhận đơn hàng):
     + KHÔNG ĐƯỢC TỰ Ý GỌI TOOL GHI DỮ LIỆU NGAY.
     + BẮT BUỘC phải liệt kê chi tiết nội dung dự định thay đổi (Tên bản ghi, Mã, Số tiền, Trạng thái cũ/mới).
     + BẮT BUỘC dừng lại và hỏi xác nhận: "Bạn có đồng ý để mình thực hiện cập nhật/tạo mới dữ liệu này vào Odoo không?"
     + CHỈ KHI NGƯỜI DÙNG PHẢN HỒI "ĐỒNG Ý / YES / CONFIRM", bạn mới được phép gọi Tool ghi dữ liệu.

2. PHONG CÁCH & TỐC ĐỘ:
   - Đi thẳng vào kết quả/báo cáo (Executive Summary). 
   - KHÔNG dùng các câu đệm, câu thoại lấp khoảng trống trước hoặc trong khi gọi Tool.

3. ĐỊNH DẠNG SỐ LIỆU & DỮ LIỆU:
   - Định dạng tiền tệ VND chuẩn (ví dụ: 19.990.000₫).
   - Luôn dùng Bảng Markdown cho danh sách có từ 2 đối tượng trở lên.

4. TÍNH TOÁN NGHIỆP VỤ (BI METRICS):
   - Khi báo cáo Doanh thu, CHỈ TÍNH các đơn trạng thái `sale` (Đã xác nhận/Đã khóa).
   - Tự động bổ sung 2 chỉ số: 
     + AOV (Giá trị trung bình/đơn = Tổng doanh thu thực tế / Số đơn thành công).
     + Pipeline Risk (Số lượng & tổng giá trị các đơn `draft` / `cancel`).

5. ĐỀ XUẤT HÀNH ĐỘNG (ACTIONABLE INSIGHTS):
   - Kết thúc báo cáo bằng 1-2 gợi ý hành động ngắn gọn (Ví dụ: đề xuất xử lý đơn nháp tồn đọng, cảnh báo sản phẩm dưới ngưỡng tồn kho).
```

---

## ⚠️ 2 Lưu ý Kỹ thuật Quan trọng khi Triển khai Enterprise MCP

1. **Tránh làm phồng Context Window bằng Base64 Image (`image_1920`)**:
   - Tránh trả dữ liệu Base64 thô của field `image_1920` qua JSON-RPC vì sẽ gây chậm/lag Claude Context.
   - Thay vào đó, trả về URL ảnh tĩnh Odoo: `https://smartshop-odoo.odoo.com/web/image/product.template/{id}/image_128` để Claude render bằng Markdown tag `![alt](url)`.

2. **Phân biệt Doanh thu Thực tế (`sale`) vs Pipeline (`draft`) vs Cancelled (`cancel`)**:
   - Chỉ tính đơn `state == 'sale'` vào Doanh thu Thực tế và AOV.
   - Đơn `state == 'draft'` xếp vào Doanh thu Tiềm năng (Pipeline).
   - Đơn `state == 'cancel'` hoàn toàn loại bỏ khỏi doanh thu.

---

## Các Data Models cốt lõi trong Odoo
* `product.template`: Thông tin sản phẩm (`name`, `list_price`, `standard_price`, `qty_available`, `is_published`).
* `res.partner`: Thông tin khách hàng/doanh nghiệp (`name`, `email`, `phone`, `city`).
* `sale.order`: Đơn hàng bán (`name`, `partner_id`, `amount_total`, `state`, `date_order`).
* `account.move`: Hóa đơn bán hàng & thanh toán (`name`, `partner_id`, `amount_total`, `state`, `move_type`).
* `stock.picking`: Phiếu nhập/xuất/chuyển kho (`name`, `partner_id`, `location_id`, `location_dest_id`, `state`).
