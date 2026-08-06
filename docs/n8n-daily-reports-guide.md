# SmartShop Daily Reports — Hướng dẫn cài đặt (n8n)

Workflow gửi 2 báo cáo tự động hằng ngày qua Telegram:

| Báo cáo | Giờ chạy | Nội dung |
|---|---|---|
| ⚠️ Low Stock Alert | 08:00 sáng | Danh sách sản phẩm tồn kho <= 5 cái |
| 📊 Revenue Digest | 18:00 chiều | Tổng số đơn + tổng doanh thu đơn đã chốt (sale/done) trong ngày |

## File import

File: `n8n/smartshop-daily-reports.json`

## Cách import vào n8n

1. Mở n8n → Workflows → Import from File
2. Chọn file `n8n/smartshop-daily-reports.json`
3. Import xong, workflow sẽ hiện 2 nhánh song song (Low Stock + Revenue)

## Cấu hình Credential (bắt buộc)

Sau khi import, workflow có 2 loại node cần gán credential (2 node Odoo + 2 node Telegram):

### 1. Odoo Credential

- Mở node "Odoo: San pham ton kho <= 5" (hoặc node revenue)
- Chọn Create New Credential → loại Odoo
- Điền thông tin từ `.env`:

| Field | Giá trị |
|---|---|
| Site URL | `https://smartshop-odoo.odoo.com` |
| Database | `smartshop-odoo` |
| Username | `nhatlovely2017@gmail.com` |
| Password | Mật khẩu trong `.env` (`ODOO_PASSWORD`) |

> Lưu ý bảo mật: Password được lưu trong n8n Credential (mã hóa), KHÔNG nhúng vào JSON workflow.

### 2. Telegram Credential

- Mở node "Telegram: Gui Low Stock Alert" (hoặc node revenue)
- Chọn Create New Credential → loại Telegram API
- Dán Bot Token từ `.env` (`TELEGRAM_BOT_TOKEN`)
- Gán cùng credential cho cả 2 node Telegram

### 3. Chat ID

Mặc định gửi tới `6553206564` (admin). Muốn đổi, sửa `chat_id` trong node Code: Format Low Stock Alert và Code: Tong hop doanh thu.

## Điều chỉnh lịch chạy

Mặc định:
- Low Stock: `0 8 * * *` → 08:00 mỗi ngày
- Revenue: `0 18 * * *` → 18:00 mỗi ngày

Đổi giờ: Mở node Schedule → Trigger Times → chỉnh Cron Expression. Ví dụ Low Stock lúc 07:30 sáng: `30 7 * * *`.

## Kiểm tra workflow

1. Kích hoạt workflow (bật nút Active)
2. Chạy thử node Odoo:

### Nhánh Low Stock

- Execute node "Odoo: San pham ton kho <= 5"
- 0 dòng → không có sản phẩm tồn <= 5 (bình thường)
- Có dòng dữ liệu → Execute node Telegram để nhận tin cảnh báo

### Nhánh Revenue

- Execute node "Odoo: Don ban hom nay (sale/done)"
- Kiểm tra dữ liệu trả về có đơn hôm nay không
- Execute node "Code: Tong hop doanh thu" → xem tổng doanh thu
- Execute node Telegram → nhận báo cáo

## Xử lý sự cố

| Vấn đề | Nguyên nhân | Cách xử lý |
|---|---|---|
| Odoo node lỗi | Credential chưa gán/thiếu | Gán lại Odoo Credential |
| Không thấy 2 nhánh | Import sai file | Import lại file JSON |
| Telegram không gửi | Telegram Credential chưa đúng | Kiểm tra Bot Token, gán lại |
| Low Stock không có tin | Không có sản phẩm tồn <= 5 | Chạy node Odoo thử, kiểm tra dữ liệu |
| Báo cáo 18:00 rỗng | Chưa có đơn sale/done hôm nay | Kiểm tra đơn trên Odoo |

## Liên quan

- File workflow: `n8n/smartshop-daily-reports.json`
- Workflow approval: `n8n/n8n-workflow-a-approval-flow.json`, `n8n/n8n-workflow-b-approval-callback.json`
- Hướng dẫn security: `docs/n8n-approval-webhook-setup.md`