# 📥 Hướng dẫn Import 2 Workflow n8n Approval

Thư mục này chứa **2 file JSON** workflow n8n sẵn sàng import:

| File | Workflow | Mục đích |
|---|---|---|
| `n8n-workflow-a-approval-flow.json` | **SmartShop Approval Flow (A)** | Nhận request từ SmartShop → gửi Telegram cho Manager kèm nút ✅/❌ |
| `n8n-workflow-b-approval-callback.json` | **SmartShop Approval Callback (B)** | Lắng nghe Manager bấm nút → gọi lại SmartShop tạo/từ chối đơn |

---

## 🚀 Cách Import vào n8n

### Bước 1: Import Workflow A

1. Đăng nhập [n8n Cloud](https://odooworkflow.app.n8n.cloud)
2. Vào **Workflows** → nhấn nút **⋮** (3 chấm) hoặc **Import from File**
3. Chọn file `n8n-workflow-a-approval-flow.json`
4. Workflow **"SmartShop Approval Flow (A)"** sẽ xuất hiện

### Bước 2: Import Workflow B

1. Lặp lại tương tự với file `n8n-workflow-b-approval-callback.json`
2. Workflow **"SmartShop Approval Callback (B)"** sẽ xuất hiện

### Bước 3: Liên kết Credential Telegram

Khi import, n8n sẽ báo thiếu credential cho node **Telegram** và **Telegram Trigger**:

1. Click vào node **Telegram - Gui cho Manager** (Workflow A)
2. Trong phần **Credential**, chọn credential Telegram Bot đã có **hoặc** tạo mới:
   - Nhấn **Create New**
   - Dán `TELEGRAM_BOT_TOKEN` từ `.env`: `8835716387:AAGxnOylWpuvJP0r43RPMqM_txbagLkds5I`
   - Nhấn **Test** → **Save**
3. Lặp lại cho node **Telegram Trigger** (Workflow B) — chọn cùng credential

### Bước 4: Kiểm tra Webhook URL (Workflow A)

1. Mở node **Webhook Listener** (Workflow A)
2. Xem **Production URL** — phải là:
   ```
   https://odooworkflow.app.n8n.cloud/webhook/approval-webhook
   ```
3. Đảm bảo URL này khớp với `N8N_APPROVAL_WEBHOOK_URL` trong `.env`:
   ```
   N8N_APPROVAL_WEBHOOK_URL=https://odooworkflow.app.n8n.cloud/webhook/approval-webhook
   ```

### Bước 5: Kiểm tra Secret (Workflow B)

1. Mở node **Code - Tao HMAC Signature** (Workflow B)
2. Kiểm tra dòng:
   ```javascript
   const secret = $env.APPROVAL_WEBHOOK_SECRET || 'smartshop-approval-2026';
   ```
3. Secret phải khớp với `N8N_APPROVAL_WEBHOOK_SECRET` trong `.env`:
   ```
   N8N_APPROVAL_WEBHOOK_SECRET=smartshop-approval-2026
   ```
4. Nếu bạn đã đổi secret trong `.env`, sửa cả trong file JSON (hoặc set env var `APPROVAL_WEBHOOK_SECRET` trên n8n)

### Bước 6: Kiểm tra URL Gateway (Workflow B)

1. Mở node **HTTP Request - Goi SmartShop** (Workflow B)
2. URL phải là:
   ```
   https://smartshop-ai-gateway.onrender.com/api/webhook/approval
   ```
3. Nếu chạy local, đổi thành: `http://localhost:8000/api/webhook/approval`

### Bước 7: Bật Active

1. Nhấn **Save** trên cả 2 workflow
2. Toggle **Active** (góc phải trên) cho cả 2 workflow

---

## 🧪 Test nhanh

### Test Workflow A (nhận request)

Gửi request thử từ terminal:

```bash
curl -X POST https://odooworkflow.app.n8n.cloud/webhook/approval-webhook \
  -H "Content-Type: application/json" \
  -d "{\"order_name\":\"SO-TEST-123\",\"total_amount\":30000000,\"employee_name\":\"Kien\",\"manager_chat_id\":\"6553206564\",\"telegram_id\":\"emp10\"}"
```

→ Manager (chat_id `6553206564`) sẽ nhận tin nhắn Telegram có 2 nút ✅ Duyệt / ❌ Từ chối.

### Test Workflow B (callback)

1. Bấm nút **✅ Duyệt** trên Telegram
2. Workflow B xử lý → gọi lại SmartShop
3. SmartShop verify HMAC → tạo Sale Order trên Odoo

---

## ⚠️ Lưu ý quan trọng

| Điểm | Chi tiết |
|---|---|
| **Credential Telegram** | Phải chọn/liên kết sau khi import — n8n không tự biết credential của bạn |
| **Secret** | `smartshop-approval-2026` — phải khớp `.env` |
| **URL Gateway** | `https://smartshop-ai-gateway.onrender.com` — đổi nếu chạy local |
| **callback_data** | Giới hạn 64 ký tự — format `approve:SO-...:emp10` đủ ngắn |
| **telegram_id** | Là user_id của NHÂN VIÊN (vd `emp10`), không phải Manager |

---

## 📂 Cấu trúc thư mục

```
n8n/
├── n8n-workflow-a-approval-flow.json      ← Workflow A (Nhận + Gửi TG)
├── n8n-workflow-b-approval-callback.json  ← Workflow B (Callback + Gọi lại)
└── README-IMPORT.md                       ← File này