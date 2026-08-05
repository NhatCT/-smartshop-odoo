# 📡 Hướng dẫn Config n8n Approval Webhook Secret

## 🔄 Tổng quan luồng Approval

```
SmartShop Gateway                n8n Cloud
─────────────────                ─────────
1. AI tạo đơn > 20tr
2. Gửi request duyệt ──────────→  Webhook nhận (approval-webhook)
   (auth.py: send_approval_request)
3.                          Manager bấm Approve/Reject trên Telegram
4.                          n8n gọi lại ──→ POST /api/webhook/approval
                              với header:
                              X-Webhook-Signature: HMAC-SHA256(body)
5. Gateway xác minh chữ ký
6. Tạo/Từ chối đơn trên Odoo
```

---

## 🔐 Cơ chế chữ ký (Signature) — BẮT BUỘC khớp cả 2 phía

### Server SmartShop (đã có sẵn — không cần sửa)

File `app.py` — endpoint `POST /api/webhook/approval`:

```python
def _verify_sig(payload: bytes, sig: str) -> bool:
    secret = _get_webhook_secret()  # Đọc từ env N8N_APPROVAL_WEBHOOK_SECRET
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)

@app.post("/api/webhook/approval")
async def approval_callback(request: Request):
    raw = await request.body()
    sig = request.headers.get("X-Webhook-Signature", "")
    if not _verify_sig(raw, sig):
        return {"status": "error", "message": "Invalid signature"}, 401
    ...
```

**Công thức**: `X-Webhook-Signature = HMAC_SHA256(secret, raw_request_body).hexdigest()`

> ⚠️ RAW BODY — KHÔNG phải JSON string đã parse. Phải dùng đúng chuỗi bytes của body gửi đi.

---

## 📋 Cấu hình trên n8n (6 bước)

### Bước 1: Lấy Secret từ `.env` hoặc Render

Secret hiện tại trong `.env`:

```env
N8N_APPROVAL_WEBHOOK_SECRET=smartshop-approval-2026
```

Nếu deploy trên Render → vào **Render Dashboard → smartshop-ai-gateway → Environment** và lấy giá trị `N8N_APPROVAL_WEBHOOK_SECRET`.

> 🔑 Secret phải GIỐNG HỆT ở cả n8n và SmartShop.

### Bước 2: Lưu Secret trên n8n (Credentials hoặc Env)

**Cách A — Dùng n8n Environment Variable (Cloud/Production dùng):**
1. Vào **n8n Settings → Environment Variables** (chỉ khả dụng bản Cloud/Enterprise)
2. Thêm:
   - Name: `APPROVAL_WEBHOOK_SECRET`
   - Value: `smartshop-approval-2026`

**Cách B — Dùng Credentials (cách phổ biến hơn):**
1. Vào **n8n Dashboard → Credentials → Add Credential**
2. Chọn type: **Header Auth** (hoặc **Text** nếu tự lưu)
3. Đặt:
   - Name: `SmartShop Approval Secret`
   - Header Name: `X-Webhook-Signature`
   - Header Value: *(tạm để trống, sẽ được thay bằng code tạo chữ ký)*

### Bước 3: Mở workflow Approval hiện tại

Workflow **"Approval Workflow"** trong n8n có 2 phần:

- **Phần 1 — Webhook NHẬN** (đã có): nhận request gửi từ SmartShop → gửi notification cho Manager
- **Phần 2 — Gọi LẠI SmartShop**: Sau khi Manager approve/reject, gọi ngược về SmartShop

### Bước 4: Thêm Code node tạo chữ ký HMAC

Chèn 1 **Code node** ngay TRƯỚC **HTTP Request node** (nút gọi về SmartShop):

**Code node content:**

```javascript
// Lấy secret — dùng env var hoặc credential
const secret = $env.APPROVAL_WEBHOOK_SECRET || 'smartshop-approval-2026';

// Đọc dữ liệu từ workflow (action + order_name + telegram_id)
const action = $input.first().json.action;        // "approve" hoặc "reject"
const orderName = $input.first().json.order_name;
const telegramId = $input.first().json.telegram_id;

// Tạo payload JSON — phải giống HỆT JSON.stringify chuẩn
const body = JSON.stringify({
  action: action,
  order_name: orderName,
  telegram_id: telegramId,
});

// Tạo HMAC-SHA256 signature
const crypto = require('crypto');
const signature = crypto
  .createHmac('sha256', secret)
  .update(body)
  .digest('hex');

return {
  body: body,
  headers: {
    'X-Webhook-Signature': signature,
    'Content-Type': 'application/json',
  },
};
```

> ⚠️ **LƯU Ý QUAN TRỌNG**: `JSON.stringify` trong n8n (Code node) phải tạo ra chuỗi **GIỐNG HỆT** bytes mà HTTP Request node gửi đi. Cách an toàn nhất:
> - HTTP Request node dùng **JSON Body** — n8n tự `JSON.stringify()` với thứ tự key giữ nguyên như đã khai báo.
> - Trong Code node, khai báo body với **cùng thứ tự key** như trong HTTP Request node.
> - Hoặc tốt hơn: **body = $json.body** (lấy trực tiếp từ Code node output).

### Bước 5: Cấu hình HTTP Request node gọi về SmartShop

Node **HTTP Request** gọi về gateway:

| Field | Giá trị |
|---|---|
| **Method** | `POST` |
| **URL** | `https://smartshop-ai-gateway.onrender.com/api/webhook/approval` |
| **Body Content Type** | `JSON` |
| **Body** | `={{ $json.body }}` (lấy từ Code node) |
| **Header X-Webhook-Signature** | `={{ $json.headers['X-Webhook-Signature'] }}` |
| **Header Content-Type** | `application/json` |

> 🌐 Nếu chạy local: URL = `http://localhost:8000/api/webhook/approval`

### Bước 6: Test toàn bộ flow

1. **Test Code node riêng**: bấm *Execute node* → xem output `signature` có đúng 64 ký tự hex (HMAC-SHA256) không.
2. **Test HTTP Request node**: bấm *Execute node* → phải nhận response `{"status": "ok", ...}`.
3. **Test End-to-End**: 
   - Gõ trên Telegram: "Tạo đơn 30tr cho khách Alice 5 Laptop"
   - Đơn bị Approval Gate chặn → n8n nhận request
   - Manager bấm Approve
   - n8n gọi lại SmartShop với signature đúng
   - SmartShop verify → tạo Sale Order trên Odoo

---

## 🧪 Tự kiểm tra chữ ký (trước khi gọi SmartShop)

Chạy script Python này để generate chuẩn signature:

```python
import hashlib, hmac, json

secret = "smartshop-approval-2026"
body = json.dumps({
    "action": "approve",
    "order_name": "SO-emp10-1785921922",
    "telegram_id": "emp10",
})

sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
print("Signature:", sig)
print("Payload:", body)

# Kết quả phải có 64 ký tự hex — ví dụ:
# Signature: f68b402e47998cf5211f03b5114134a711927dffc05983815f1c3748302d5f3c
```

> Nếu SmartShop trả về `{"status": "error", "message": "Invalid signature"}` → chữ ký không khớp.

---

## ❌ 📋 Checklist Debug "Invalid signature"

| Kiểm tra | Chi tiết |
|---|---|
| ✅ Secret giống nhau | n8n phải dùng đúng `N8N_APPROVAL_WEBHOOK_SECRET` (không dư space, không khác case) |
| ✅ Raw body | Signature tính trên **RAW BYTES** của body, KHÔNG phải body đã format/pretty-print |
| ✅ Header đúng tên | Header key chính xác là `X-Webhook-Signature` (case-insensitive nhưng phải có dấu `-`) |
| ✅ Thuật toán | Phải là `HMAC-SHA256` (không phải SHA256 thuần, không phải SHA1, không phải MD5) |
| ✅ Hex encode | `hexdigest()` — 64 ký tự chữ thường a-f0-9 |
| ✅ Content-Type | Gửi `Content-Type: application/json` |
| ✅ URL đúng | `https://<host>/api/webhook/approval` (có `/api/webhook/approval` ở cuối) |

---

## 🔒 Gợi ý đổi Secret (bảo mật)

Khi muốn đổi secret mới:

**1. Sinh secret mới** (ít nhất 32 ký tự):
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**2. Cập nhật trên Render**:
- Render Dashboard → service `smartshop-ai-gateway` → **Environment**
- Sửa `N8N_APPROVAL_WEBHOOK_SECRET` → lưu → Deploy

**3. Cập nhật trên n8n**:
- Sửa credential / env var `APPROVAL_WEBHOOK_SECRET` → Save

**4. Kiểm tra**: chạy lại test webhook (bước 6).

---

## 📂 File liên quan

| File | Vai trò |
|---|---|
| `app.py` | Định nghĩa endpoint `/api/webhook/approval` + verify HMAC signature |
| `auth.py` | Hàm `send_approval_request()` gửi request duyệt tới n8n |
| `ai.py` | Hàm `approve_order()` / `reject_order()` xử lý approve/reject |
| `.env` | `N8N_APPROVAL_WEBHOOK_SECRET=smartshop-approval-2026` |
| `render.yaml` | Khai báo env var `N8N_APPROVAL_WEBHOOK_SECRET` trên Render |