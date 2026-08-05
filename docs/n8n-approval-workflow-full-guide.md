# 🚀 Hướng dẫn xây dựng toàn bộ n8n Approval Workflow từ đầu

> Hướng dẫn này đi từ **0 → 100%**: tạo workflow, cấu hình webhook, gửi Telegram, và gọi lại SmartShop Gateway.

---

## 🧠 Hiểu kiến trúc trước khi làm

```
┌─────────────────────────────┐         ┌──────────────────────────────┐
│    SmartShop Gateway        │         │           n8n Cloud          │
│    (Render / local)         │         │                              │
│                             │         │  ┌────────────────────────┐  │
│  1. AI tạo đơn > 20tr       │         │  │ Webhook NHẬN           │  │
│  2. Gọi send_approval_      │────────▶│  │ /webhook/approval-     │  │
│     request()               │  POST   │  │   webhook              │  │
│                             │         │  └──────────┬─────────────┘  │
│                             │         │             ▼               │
│                             │         │  ┌────────────────────────┐  │
│                             │         │  │ Telegram gửi thông báo  │  │
│                             │         │  │ cho Manager + nút bấm   │  │
│                             │         │  └──────────┬─────────────┘  │
│                             │         │             ▼               │
│                             │         │  ┌────────────────────────┐  │
│                             │         │  │ Manager bấm nút        │  │
│                             │         │  │ Approve / Reject       │  │
│                             │         │  └──────────┬─────────────┘  │
│                             │         │             ▼               │
│                             │         │  ┌────────────────────────┐  │
│  ┌──────────────────────┐   │         │  │ Code node tạo chữ ký    │  │
│  │ POST /api/webhook/   │◀───────────│  │ HMAC-SHA256             │  │
│  │ approval             │  POST      │  └──────────┬─────────────┘  │
│  │ X-Webhook-Signature  │            │             ▼               │
│  └──────────┬───────────┘            │  ┌────────────────────────┐  │
│             ▼                        │  │ HTTP Request gọi lại    │  │
│  Tạo/Từ chối đơn trên Odoo            │  │ SmartShop Gateway       │  │
└─────────────────────────────┘         │  └────────────────────────┘  │
                                        └──────────────────────────────┘
```

---

## 📋 BƯỚC 1: Lấy thông tin cần thiết

### Từ project SmartShop:

| Thông tin | Giá trị hiện tại |
|---|---|
| Webhook URL nhận approval | `https://odooworkflow.app.n8n.cloud/webhook/approval-webhook` |
| Webhook Secret | `smartshop-approval-2026` |
| Gateway URL (khi deploy Render) | `https://smartshop-ai-gateway.onrender.com` |
| Gateway URL (local) | `http://localhost:8000` |
| Endpoint approve/reject | `POST /api/webhook/approval` |
| Telegram Bot Token | `8835716387:AAGxnOylWpuvJP0r43RPMqM_txbagLkds5I` |
| Manager Chat ID | `6553206564` |

> ⚠️ Các giá trị trên lấy từ file `.env` của project. Nếu bạn đã đổi thì dùng giá trị mới.

---

## 📋 BƯỚC 2: Tạo workflow mới trên n8n

1. Đăng nhập [n8n Cloud](https://n8n.io) (hoặc n8n self-hosted)
2. Vào **Workflows** → nhấn **+ Add Workflow**
3. Đặt tên: **SmartShop Approval Flow**
4. Nhấn **Save** để lưu tên

> 💡 Chúng ta sẽ xây dựng **HAI workflow riêng biệt**:
> - **Workflow A** — NHẬN approval request từ SmartShop → gửi Telegram
> - **Workflow B** — NHẬN callback khi Manager bấm nút → gọi lại SmartShop
>
> Cách này tách biệt trách nhiệm rõ ràng và dễ debug.

---

# 🔵 WORKFLOW A: Nhận approval request → Gửi Telegram cho Manager

---

## 📋 BƯỚC 3: Thêm Webhook node (NHẬN request từ SmartShop)

### 3.1 Thêm node **Webhook**

1. Trong Workflow A, nhấn **+** → tìm **Webhook**
2. Cấu hình:

| Field | Giá trị |
|---|---|
| **Webhook Type** | `When Received` |
| **HTTP Method** | `POST` |
| **Path** | `approval-webhook` |
| **Response Mode** | `On Received` |
| **Respond** | `Using 'Respond to Webhook' Node` |
| **Authentication** | `None` (hoặc `Header Auth` nếu muốn bảo mật) |

### 3.2 Lấy URL webhook

Sau khi tạo node, n8n hiển thị **Production URL** và **Test URL**:

```
Production: https://odooworkflow.app.n8n.cloud/webhook/approval-webhook
Test:      https://odooworkflow.app.n8n.cloud/webhook-test/approval-webhook
```

> ✅ URL này phải khớp với `N8N_APPROVAL_WEBHOOK_URL` trong `.env` của SmartShop.

**Payload nhận được từ SmartShop** (từ `auth.py:send_approval_request`):

```json
{
  "order_name": "SO-emp10-1785921922",
  "total_amount": 50000000.0,
  "employee_name": "Sales Staff",
  "manager_chat_id": "6553206564",
  "telegram_id": "emp10"
}
```

> ℹ️ **`telegram_id`** chính là user_id của nhân viên gửi yêu cầu (vd: `emp10`). Đây là key dùng để xác định draft đơn của ai khi Manager approve — **bắt buộc phải truyền lại** khi gọi về SmartShop.

---

## 📋 BƯỚC 4: Code node — Chuẩn bị tin nhắn Telegram + Nút bấm

### 4.1 Thêm node **Code**

1. Nhấn **+** sau Webhook node → chọn **Code**
2. Dán code sau:

```javascript
// Lấy dữ liệu từ Webhook
const data = $input.first().json;

const orderName = data.order_name;
const total = Number(data.total_amount || 0);
const employee = data.employee_name || 'N/A';
const managerChatId = data.manager_chat_id || '6553206564';
const userId = data.telegram_id || '';  // user_id của nhân viên

// Format tiền VNĐ
const formattedTotal = total.toLocaleString('vi-VN');

// Chuẩn bị nội dung tin nhắn
const messageText = `📋 *YÊU CẦU PHÊ DUYỆT ĐƠN HÀNG*\n\n`
  + `• Mã đơn: \`${orderName}\`\n`
  + `• Nhân viên: ${employee}\n`
  + `• Tổng tiền: *${formattedTotal} VNĐ*\n\n`
  + `Vui lòng kiểm tra và phê duyệt:`;

// ⚠️ NHÚNG telegram_id VÀO callback_data (giới hạn 64 ký tự)
// Format: <action>:<order_name>:<telegram_id>
// Ví dụ:  approve:SO-emp10-1785921922:emp10  = 33 ký tự — OK!
const approveCb = `approve:${orderName}:${userId}`;
const rejectCb = `reject:${orderName}:${userId}`;

return [{
  json: {
    chat_id: managerChatId,
    text: messageText,
    reply_markup: {
      inline_keyboard: [[
        { text: '✅ Duyệt', callback_data: approveCb },
        { text: '❌ Từ chối', callback_data: rejectCb }
      ]]
    }
  }
}];
```

> ⚠️ **LƯU Ý**: `callback_data` Telegram giới hạn **64 ký tự**. Kiểm tra:
> - `approve:SO-emp10-1785921922:emp10` = 33 ký tự ✅
> - `reject:SO-emp10-1785921922:emp10` = 34 ký tự ✅
> - Nếu `order_name` quá dài (> 40 ký tự), cân nhắc rút gọn.

### 4.2 Test Code node

Nhấn **Execute node** với dữ liệu mẫu:

```json
{
  "order_name": "SO-emp10-1785921922",
  "total_amount": 50000000,
  "employee_name": "Sales Staff",
  "manager_chat_id": "6553206564",
  "telegram_id": "emp10"
}
```

Kết quả mong đợi — output chứa `chat_id`, `text`, `reply_markup` với `callback_data` dạng `approve:SO-emp10-1785921922:emp10`.

---

## 📋 BƯỚC 5: Telegram node — Gửi tin nhắn cho Manager

### 5.1 Thêm node **Telegram**

1. Nhấn **+** sau Code node (Workflow A) → chọn **Telegram**
2. **Credential**: nhấn **Create New** → dán `TELEGRAM_BOT_TOKEN` → Test → Save

### 5.2 Cấu hình Operation

| Field | Giá trị |
|---|---|
| **Operation** | `Send Message` |
| **Chat ID** | `={{ $json.chat_id }}` |
| **Text** | `={{ $json.text }}` |
| **Additional Fields** → **Reply Markup** | `={{ JSON.stringify($json.reply_markup) }}` |
| **Additional Fields** → **Parse Mode** | `Markdown` |

### 5.3 ✅ Workflow A hoàn tất!

```
[Webhook NHẬN approval] → [Code chuẩn bị TG] → [Telegram gửi cho Manager]
```

**Bật Active** cho Workflow A để bắt đầu nhận request.

---

# 🟢 WORKFLOW B: Nhận callback từ Manager → Gọi lại SmartShop

---

## 📋 BƯỚC 6: Tạo Workflow B + Telegram Trigger node

### 6.1 Tạo Workflow B

1. Vào **Workflows** → **+ Add Workflow**
2. Đặt tên: **SmartShop Approval Callback**
3. Nhấn **Save**

### 6.2 Thêm node **Telegram Trigger**

1. Nhấn **+** → tìm **Telegram Trigger**
2. Chọn credential Telegram Bot (đã tạo ở Bước 5)
3. Cấu hình:

| Field | Giá trị |
|---|---|
| **Updates** | `Callback Query` |
| **Additional Fields** → **Only Allow Calls From** | `={{ $json.message.chat.id }}` — hoặc để trống |

> 💡 **Telegram Trigger** tự động lắng nghe khi Manager bấm nút inline keyboard trên tin nhắn đã gửi.

---

## 📋 BƯỚC 7: Code node — Parse quyết định Approve/Reject

Thêm node **Code** sau Telegram Trigger:

```javascript
// Lấy dữ liệu từ Telegram callback
const cb = $input.first().json.callback_query || {};
const callbackData = cb.data || '';

// Parse callback_data format: "<action>:<order_name>:<telegram_id>"
// Ví dụ: "approve:SO-emp10-1785921922:emp10"
const parts = callbackData.split(':');
const action = parts[0];                    // "approve" hoặc "reject"
const telegramId = parts.pop();             // "emp10" — user_id của NHÂN VIÊN
const orderName = parts.slice(1).join(':'); // "SO-emp10-1785921922"

const chatId = String(cb.message?.chat?.id || '');
const fromId = String(cb.from?.id || '');
const messageId = cb.message?.message_id;

return [{
  json: {
    action: action,
    order_name: orderName,
    telegram_id: telegramId,   // ← user_id của NHÂN VIÊN (emp10)
    chat_id: chatId,
    from_id: fromId,           // ← ID của Manager bấm nút (chỉ để tham khảo)
    message_id: messageId,
    callback_query_id: cb.id
  }
}];
```

> ✅ **`telegram_id` được lấy trực tiếp từ `callback_data`** — không cần database, không cần static data. Đơn giản và chính xác.

---

## 📋 BƯỚC 8: Lưu Secret vào n8n

### 8.1 (Khuyên dùng) Dùng n8n Environment Variables

1. Vào **n8n Settings (⚙️) → Environment Variables**
2. Thêm:

| Name | Value |
|---|---|
| `APPROVAL_WEBHOOK_SECRET` | `smartshop-approval-2026` |

### 8.2 (Thay thế) Credential Header Auth

1. Vào **Credentials** → **Add Credential**
2. Chọn type: **Header Auth**
3. Cấu hình:

| Field | Giá trị |
|---|---|
| **Name** | `SmartShop Approval Secret` |
| **Header Name** | `X-Webhook-Signature` |
| **Header Value** | `smartshop-approval-2026` |

> ⚠️ **QUAN TRỌNG**: Secret phải GIỐNG HỆT `N8N_APPROVAL_WEBHOOK_SECRET` trong `.env` của SmartShop. Nếu bạn có Environment Variables (bản Cloud/Enterprise) thì dùng cách 8.1. Còn lại dùng 8.2.

---

## 📋 BƯỚC 9: Code node — Tạo HMAC-SHA256 Signature

Thêm node **Code** sau node parse (Bước 7):

```javascript
// Lấy secret — ưu tiên env var, fallback credential/hardcode
const secret = $env.APPROVAL_WEBHOOK_SECRET || 'smartshop-approval-2026';

// Lấy dữ liệu từ node trước
const data = $input.first().json;
const action = data.action;
const orderName = data.order_name;
const telegramId = data.telegram_id;

// Tạo payload — THỨ TỰ KEY PHẢI GIỮ NGUYÊN
// KHỚP với app.py: data.get("action"), data.get("order_name"), data.get("telegram_id")
const body = JSON.stringify({
  action: action,
  order_name: orderName,
  telegram_id: telegramId
});

// Tạo HMAC-SHA256 signature — KHỚP với app.py:_verify_sig
const crypto = require('crypto');
const signature = crypto
  .createHmac('sha256', secret)
  .update(body)
  .digest('hex');

return [{
  json: {
    ...data,
    body: body,
    signature: signature
  }
}];
```

**Kết quả mong đợi:**

```json
{
  "action": "approve",
  "order_name": "SO-emp10-1785921922",
  "telegram_id": "emp10",
  "body": "{\"action\":\"approve\",\"order_name\":\"SO-emp10-1785921922\",\"telegram_id\":\"emp10\"}",
  "signature": "abc123...64 ký tự hex..."
}
```

> ⚠️ **QUAN TRỌNG**: `signature` phải đúng **64 ký tự hex**. Kiểm tra bằng cách so với kết quả từ Python script bên dưới.

---

## 📋 BƯỚC 10: HTTP Request node — Gọi lại SmartShop Gateway

Thêm node **HTTP Request** sau Code node tạo signature (Bước 9):

### 10.1 Cấu hình Request

| Field | Giá trị |
|---|---|
| **Method** | `POST` |
| **URL** | `https://smartshop-ai-gateway.onrender.com/api/webhook/approval` |
| **Body Content Type** | `JSON` |
| **Body Parameters** | `={{ $json.body }}` (nhập chính xác biểu thức này) |
| **Send Headers** | Bật |

### 10.2 Cấu hình Headers (2 headers bắt buộc)

**Header 1 — X-Webhook-Signature:**
```
Key:   X-Webhook-Signature
Value: ={{ $json.signature }}
```

**Header 2 — Content-Type:**
```
Key:   Content-Type
Value: application/json
```

> 🌐 Nếu chạy local: URL = `http://localhost:8000/api/webhook/approval`

### 10.3 ✅ Workflow B hoàn tất!

```
[Telegram Trigger callback] → [Code parse] → [Code tạo signature] → [HTTP Request → SmartShop]
```

**Bật Active** cho Workflow B.

---

# 🧪 BƯỚC 11: Test toàn bộ hệ thống

### 11.1 Test Webhook NHẬN (Workflow A)

1. Dùng **n8n Webhook Test URL** hoặc Production URL: `https://odooworkflow.app.n8n.cloud/webhook/approval-webhook`
2. Mở terminal gửi request thử:

```bash
curl -X POST https://odooworkflow.app.n8n.cloud/webhook/approval-webhook \
  -H "Content-Type: application/json" \
  -d "{\"order_name\":\"SO-TEST-123\",\"total_amount\":30000000,\"employee_name\":\"Kien\",\"manager_chat_id\":\"6553206564\",\"telegram_id\":\"emp10\"}"
```

3. Kiểm tra Manager nhận tin nhắn Telegram có 2 nút ✅ Duyệt / ❌ Từ chối.

### 11.2 Test chữ ký HMAC (trước khi gọi SmartShop)

Chạy Python script này để verify signature n8n tạo ra có đúng không:

```python
import hashlib, hmac, json

secret = "smartshop-approval-2026"
body = json.dumps({
    "action": "approve",
    "order_name": "SO-TEST-123",
    "telegram_id": "emp10",
})

sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
print("Body     :", body)
print("Signature:", sig)
print("Length   :", len(sig), "(phải = 64)")
```

> Khi test trong n8n, dùng **đúng body giống hệt** với body đã dùng tạo signature.

### 11.3 Test End-to-End hoàn chỉnh

**Bước 1** — Từ SmartShop: gõ trên Telegram: "Tạo đơn 30tr cho khách Alice 5 Laptop"
- Approval Gate chặn → gửi request tới n8n Webhook

**Bước 2** — Manager nhận tin nhắn Telegram có 2 nút ✅ Duyệt / ❌ Từ chối.

**Bước 3** — Manager bấm **✅ Duyệt** → Workflow B xử lý → gọi lại SmartShop với signature đúng.

**Bước 4** — SmartShop verify HMAC → tạo Sale Order trên Odoo.
- Kết quả trả về: `{"status": "ok", "message": "✅ **SO-...** đã được PHÊ DUYỆT và tạo trên Odoo (ID: ...)."}`

---

# 📋 BƯỚC 12: Bật Production

1. **Workflow A**: Toggle **Active** → nhận request từ Production URL `https://odooworkflow.app.n8n.cloud/webhook/approval-webhook`
2. **Workflow B**: Toggle **Active** → lắng nghe callback từ Telegram

> ⚠️ Khi chuyển từ Test sang Production, URL thay đổi:
> - Test: `/webhook-test/approval-webhook`
> - Production: `/webhook/approval-webhook`
> 
> Đảm bảo `.env` của SmartShop dùng đúng **Production URL**.

---

# 🧪 Debug Checklist

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| SmartShop không gửi được request | Sai URL webhook | Kiểm tra `N8N_APPROVAL_WEBHOOK_URL` trong `.env` khớp Production URL |
| Manager không nhận Telegram | Sai Chat ID / bot chưa start chat | Kiểm tra `manager_chat_id`; bấm /start với bot trước |
| Bấm nút không có phản hồi | Workflow B chưa Active / Telegram Trigger sai Updates type | Bật Active; chọn `Callback Query` trong Telegram Trigger |
| `Invalid signature` từ SmartShop | Chữ ký không khớp | Kiểm tra: secret, raw body, thuật toán HMAC-SHA256, hex 64 ký tự |
| 404 khi gọi SmartShop | Sai URL gateway | Kiểm tra URL đúng `https://smartshop-ai-gateway.onrender.com/api/webhook/approval` |
| Order không tạo trên Odoo | `telegram_id` sai | Đảm bảo `telegram_id` trong payload là **user_id của NHÂN VIÊN** (vd `emp10`), lấy từ callback_data |

---

# 📚 Tóm tắt — Các workflow & node

## Workflow A: SmartShop Approval Flow
| # | Node | Mục đích |
|---|---|---|
| 1 | **Webhook** (POST) | Nhận approval request từ SmartShop (`/webhook/approval-webhook`) |
| 2 | **Code** | Chuẩn bị tin nhắn Telegram + inline keyboard (nhúng telegram_id) |
| 3 | **Telegram** | Gửi thông báo cho Manager |

## Workflow B: SmartShop Approval Callback
| # | Node | Mục đích |
|---|---|---|
| 1 | **Telegram Trigger** | Lắng nghe callback khi Manager bấm nút |
| 2 | **Code** | Parse action + order_name + telegram_id từ callback_data |
| 3 | **Code** | Tạo HMAC-SHA256 signature |
| 4 | **HTTP Request** | POST gọi lại SmartShop `/api/webhook/approval` |

---

# 📂 File tham khảo trong project

| File | Vai trò |
|---|---|
| `auth.py` | `send_approval_request()` — gửi request duyệt tới n8n (bao gồm `telegram_id`) |
| `app.py` | `POST /api/webhook/approval` — nhận callback từ n8n + verify HMAC |
| `ai.py` | `approve_order()` / `reject_order()` — tạo/từ chối đơn trên Odoo |
| `.env` | `N8N_APPROVAL_WEBHOOK_URL`, `N8N_APPROVAL_WEBHOOK_SECRET`, `TELEGRAM_BOT_TOKEN` |
| `render.yaml` | Env vars khi deploy Render |