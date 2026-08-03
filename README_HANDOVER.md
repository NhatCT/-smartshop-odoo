# 🚀 HƯỚNG DẪN BÀN GIAO & TRẢI NGHIỆM LIVE DEMO
**Dự án:** SmartShop Odoo 19 AI Gateway (Telegram Integration)  
**Dành cho:** Anthony (`anthony@technext.asia`)  
**Người khởi tạo:** Nguyễn Thành Nhật — AITECHNEXT Co., Ltd


## 2. 📱 BẮT ĐẦU TRẢI NGHIỆM TRÊN TELEGRAM

1. Mở ứng dụng **Telegram** trên smartphone hoặc máy tính.
2. Tìm kiếm Bot Telegram chính thức: **`@SmartShop_Odoo_AI_Bot`** (hoặc truy cập qua Telegram Bot Token đã cấp).
3. Bấm nút **`/start`**.

---

## 3. 🛡️ QUY TRÌNH XÁC THỰC ZERO-TRUST & PHÂN QUYỀN

### Bước 1: Đăng ký xác thực Email
Gõ lệnh đăng ký email Odoo của bạn:
```text
/register nhatlovely2017@gmail.com
--quan tri vien--
/register 2251052082nhat@ou.edu.vn
--Nhan vien kho--
/register thanhnhatcareer@gmail.com
--ke toan--
```
📌 *Mã OTP 6 số bảo mật sẽ được gửi thẳng về hộp thư Email đại diện qua n8n Gmail SMTP. OTP không bao giờ hiển thị trên Telegram chat.*

### Bước 2: Nhập mã OTP
```text
/verify 123456
```
*(Thay 123456 bằng mã OTP thực tế nhận trong Email)*

### Bước 3: Kiểm tra thông tin phân quyền
```text
/my_role
```
AI sẽ hiển thị Vai trò (Role), Quyền hạn và Engine đang chạy (~65 VNĐ/prompt).

---

## 4. 🧪 CÁC CÂU HỎI MẪU THỬ NGHIỆM (TEST CASES)

### A. Tra cứu Tồn kho & Báo giá sản phẩm (Real-time Stock & Price)
* `"giá củ sạc Anker 65W"`
* `"iPhone 15 Pro Max còn hàng không"`
* `"kiểm tra tồn kho kho HCM"`

### B. Tạo Đơn hàng Nháp (Draft Sales Order `sale.order`)
* `"tạo báo giá 2 củ sạc Anker 65W cho khách hàng Nguyen Thanh Nhat"`

### C. Quản lý Bộ nhớ AI Chat
* `/clear` hoặc `/reset`: Xóa sạch bộ nhớ hội thoại để chuyển chủ đề mới.

---

## 📊 KẾT QUẢ ĐẠT ĐƯỢC THEO OKRs:
* **Độ trễ phản hồi:** `< 1.0 giây` (Warm MCP Session)
* **Chi phí Token:** `~$0.0025 USD / prompt` (~65 VNĐ / lần hỏi)
* **Độ chính xác gọi Tool:** `≥ 95%`
* **Zero-Trust Security:** Định danh Odoo LIVE 100%
