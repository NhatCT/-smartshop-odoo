"""Test chuyên biệt cho Workflow Approve — SmartShop AI Gateway v3.0."""

import asyncio
import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["ODOO_URL"] = "https://test.odoo.com"
os.environ["ODOO_DB"] = "test"
os.environ["ODOO_USERNAME"] = "admin@test.com"
os.environ["ODOO_PASSWORD"] = "test-pass"
os.environ["N8N_APPROVAL_WEBHOOK_URL"] = "https://test.n8n.cloud/webhook/approval-webhook"
os.environ["N8N_APPROVAL_WEBHOOK_SECRET"] = "test-secret-123"
os.environ["ADMIN_CHAT_ID"] = "6553206564"


class _Tool:
    def __init__(self, name, desc="desc"):
        self.name = name
        self.description = desc
        self.input_schema = {"type": "object", "properties": {}}


class _ToolUse:
    def __init__(self, name, tid, args):
        self.name = name
        self.id = tid
        self.input = args
        self.type = "tool_use"


class _Text:
    def __init__(self, text):
        self.text = text
        self.type = "text"


def _resp(blocks):
    r = MagicMock()
    r.content = blocks
    return r


class ApprovalWorkflowTest(unittest.TestCase):
    """Test toàn bộ workflow approve: gate → n8n → webhook → tạo đơn."""

    # ─── 1. TEST APPROVAL GATE KÍCH HOẠT ───
    @patch("ai.get_client")
    def test_1_approval_gate_blocks_large_order(self, mock_client_fn):
        """Đơn > 20tr phải bị chặn và chuyển xin duyệt."""
        import ai

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _resp([_ToolUse("create_sale_order", "t1", {"model": "sale.order"})]),
            _resp([_Text("### 📋 KẾT LUẬN\nĐơn đã chuyển xin duyệt Manager.")]),
        ]
        mock_client_fn.return_value = mock_client

        mock_mcp = MagicMock()
        mock_mcp.list_tools = AsyncMock(return_value=MagicMock(tools=[_Tool("create_sale_order")]))

        # Tạo draft > 20tr
        ai.clear_draft("emp1")
        ai.clear_memory("emp1")
        d = ai.get_draft("emp1")
        d.customer_id = 5
        d.customer_name = "Alice"
        d.items.append(ai.DraftItem(10, "Laptop Dell", qty=5, unit_price=6_000_000))  # 30tr

        # Mock send_approval_request
        ai.send_approval_request = MagicMock(return_value=True)

        result = asyncio.run(ai.handle_message("emp1", "Tạo đơn 30tr", {
            "email": "sales@test.com", "full_name": "Sales Staff", "role_category": "sales_staff",
            "allowed_tools": ["create_sale_order"],
            "allowed_models": ["sale.order", "product.template"],
        }, mock_mcp))

        # Verify: không gọi MCP tool, có gửi approval request
        mock_mcp.call_tool.assert_not_called()
        ai.send_approval_request.assert_called_once()
        print(f"\n✅ [TEST 1] Approval gate chặn đơn 30tr. Kết quả: {result[:80]}...")

    # ─── 2. TEST ĐƠN NHỎ KHÔNG BỊ CHẶN ───
    @patch("ai.get_client")
    def test_2_small_order_passes_gate(self, mock_client_fn):
        """Đơn < 20tr không bị chặn bởi approval gate."""
        import ai

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _resp([_ToolUse("create_sale_order", "t2", {"model": "sale.order"})]),
            _resp([_Text("### 📋 KẾT LUẬN\nĐơn đã tạo thành công.")]),
        ]
        mock_client_fn.return_value = mock_client

        mock_mcp = MagicMock()
        mock_mcp.list_tools = AsyncMock(return_value=MagicMock(tools=[_Tool("create_sale_order")]))
        mock_mcp.call_tool = AsyncMock(return_value=MagicMock(content=[_Text('{"result": [{"id": 100}]}')]))

        # Tạo draft < 20tr
        ai.clear_draft("emp2")
        ai.clear_memory("emp2")
        d = ai.get_draft("emp2")
        d.customer_id = 5
        d.customer_name = "Bob"
        d.items.append(ai.DraftItem(20, "iPhone 15", qty=2, unit_price=5_000_000))  # 10tr

        ai.send_approval_request = MagicMock(return_value=True)

        result = asyncio.run(ai.handle_message("emp2", "Tạo đơn 10tr", {
            "email": "sales@test.com", "full_name": "Sales Staff", "role_category": "sales_staff",
            "allowed_tools": ["create_sale_order"],
            "allowed_models": ["sale.order", "product.template"],
        }, mock_mcp))

        # Verify: MCP tool được gọi, KHÔNG gửi approval
        mock_mcp.call_tool.assert_called_once()
        ai.send_approval_request.assert_not_called()
        print(f"\n✅ [TEST 2] Đơn 10tr không bị chặn. MCP tool được gọi: {mock_mcp.call_tool.call_args}")

    # ─── 3. TEST WEBHOOK CALLBACK APPROVE ───
    def test_3_webhook_approve_callback(self):
        """Webhook approve từ n8n phải tạo đơn trên Odoo."""
        import ai
        from app import approval_callback
        from fastapi import Request

        # Setup draft + order ref
        ai.clear_draft("emp3")
        d = ai.get_draft("emp3")
        d.customer_id = 5
        d.customer_name = "Alice"
        d.items.append(ai.DraftItem(10, "Laptop", qty=5, unit_price=6_000_000))  # 30tr
        d.status = "BUILDING"
        ai.register_order_ref("emp3", "SO-emp3-12345")

        # Mock Odoo create
        ai._odoo.create = MagicMock(return_value=999)

        # Tạo payload + signature
        payload = json.dumps({
            "action": "approve",
            "order_name": "SO-emp3-12345",
            "telegram_id": "emp3"
        }).encode()

        sig = hmac.new(b"test-secret-123", payload, hashlib.sha256).hexdigest()

        # Mock Request
        mock_request = MagicMock(spec=Request)
        mock_request.body = AsyncMock(return_value=payload)
        mock_request.headers = {"X-Webhook-Signature": sig}
        mock_request.json = AsyncMock(return_value=json.loads(payload))

        # Gọi webhook
        result = asyncio.run(approval_callback(mock_request))

        # Verify — result có thể là dict hoặc tuple (dict, status_code)
        if isinstance(result, tuple):
            result = result[0]
        self.assertEqual(result["status"], "ok")
        ai._odoo.create.assert_called_once()
        print(f"\n✅ [TEST 3] Webhook approve thành công: {result}")

    # ─── 4. TEST WEBHOOK REJECT ───
    def test_4_webhook_reject_callback(self):
        """Webhook reject từ n8n phải xóa draft."""
        import ai
        from app import approval_callback
        from fastapi import Request

        # Setup draft + order ref
        ai.clear_draft("emp4")
        d = ai.get_draft("emp4")
        d.customer_id = 5
        d.customer_name = "Alice"
        d.items.append(ai.DraftItem(10, "Laptop", qty=5, unit_price=6_000_000))
        ai.register_order_ref("emp4", "SO-emp4-12345")

        # Tạo payload + signature
        payload = json.dumps({
            "action": "reject",
            "order_name": "SO-emp4-12345",
            "telegram_id": "emp4"
        }).encode()

        sig = hmac.new(b"test-secret-123", payload, hashlib.sha256).hexdigest()

        mock_request = MagicMock(spec=Request)
        mock_request.body = AsyncMock(return_value=payload)
        mock_request.headers = {"X-Webhook-Signature": sig}
        mock_request.json = AsyncMock(return_value=json.loads(payload))

        result = asyncio.run(approval_callback(mock_request))

        # Verify: draft đã bị xóa
        if isinstance(result, tuple):
            result = result[0]
        self.assertEqual(result["status"], "ok")
        self.assertNotIn("emp4", ai._drafts)
        print(f"\n✅ [TEST 4] Webhook reject thành công: {result}")

    # ─── 5. TEST WEBHOOK SIGNATURE SAI ───
    def test_5_webhook_invalid_signature(self):
        """Webhook với signature sai phải bị từ chối (401)."""
        from app import approval_callback
        from fastapi import Request

        payload = json.dumps({
            "action": "approve",
            "order_name": "SO-emp5-12345",
            "telegram_id": "emp5"
        }).encode()

        # Signature SAI
        mock_request = MagicMock(spec=Request)
        mock_request.body = AsyncMock(return_value=payload)
        mock_request.headers = {"X-Webhook-Signature": "wrong-signature"}
        mock_request.json = AsyncMock(return_value=json.loads(payload))

        result = asyncio.run(approval_callback(mock_request))

        self.assertEqual(result[0]["status"], "error")
        self.assertEqual(result[1], 401)
        print(f"\n✅ [TEST 5] Webhook signature sai bị từ chối: {result[0]}")

    # ─── 6. TEST TELEGRAM INLINE BUTTON APPROVE ───
    def test_6_telegram_inline_approve(self):
        """Bấm nút Approve trên Telegram phải tạo đơn."""
        import ai
        from auth import generate_approval_token, verify_approval_token
        from app import handle_callback

        # Setup draft + order ref
        ai.clear_draft("emp6")
        d = ai.get_draft("emp6")
        d.customer_id = 5
        d.customer_name = "Alice"
        d.items.append(ai.DraftItem(10, "Laptop", qty=5, unit_price=6_000_000))
        ai.register_order_ref("emp6", "SO-emp6-12345")

        # Mock Odoo create
        ai._odoo.create = MagicMock(return_value=888)

        # Tạo approval token
        token = generate_approval_token("SO-emp6-12345", "6553206564")
        self.assertTrue(verify_approval_token("SO-emp6-12345", "6553206564", token))

        # Mock callback data: approve_SO-emp6-12345_<token>
        callback = {
            "id": "cb123",
            "data": f"approve_SO-emp6-12345_{token}",
            "from": {"id": 6553206564}
        }

        # Mock tg_send
        with patch("app.tg_send", new_callable=AsyncMock) as mock_send:
            asyncio.run(handle_callback(callback, None))
            mock_send.assert_called_once()
            msg = mock_send.call_args[0][1]
            self.assertIn("PHÊ DUYỆT", msg)
            print(f"\n✅ [TEST 6] Telegram inline approve thành công: {msg[:80]}...")

    # ─── 7. TEST TELEGRAM INLINE REJECT ───
    def test_7_telegram_inline_reject(self):
        """Bấm nút Reject trên Telegram phải xóa draft."""
        import ai
        from auth import generate_approval_token
        from app import handle_callback

        # Setup draft + order ref
        ai.clear_draft("emp7")
        d = ai.get_draft("emp7")
        d.customer_id = 5
        d.customer_name = "Alice"
        d.items.append(ai.DraftItem(10, "Laptop", qty=5, unit_price=6_000_000))
        ai.register_order_ref("emp7", "SO-emp7-12345")

        token = generate_approval_token("SO-emp7-12345", "6553206564")

        callback = {
            "id": "cb456",
            "data": f"reject_SO-emp7-12345_{token}",
            "from": {"id": 6553206564}
        }

        with patch("app.tg_send", new_callable=AsyncMock) as mock_send:
            asyncio.run(handle_callback(callback, None))
            mock_send.assert_called_once()
            msg = mock_send.call_args[0][1]
            self.assertIn("từ chối", msg.lower())
            self.assertNotIn("emp7", ai._drafts)
            print(f"\n✅ [TEST 7] Telegram inline reject thành công: {msg[:80]}...")

    # ─── 8. TEST APPROVAL TOKEN HẾT HẠN ───
    def test_8_approval_token_expired(self):
        """Token hết hạn phải bị từ chối."""
        from auth import generate_approval_token, verify_approval_token

        # Tạo token với TTL = 1 giây
        token = generate_approval_token("SO-emp8-12345", "6553206564", ttl=1)
        time.sleep(2)  # Đợi hết hạn

        self.assertFalse(verify_approval_token("SO-emp8-12345", "6553206564", token))
        print("\n✅ [TEST 8] Token hết hạn bị từ chối đúng.")

    # ─── 9. TEST APPROVAL TOKEN SAI ───
    def test_9_approval_token_invalid(self):
        """Token sai phải bị từ chối."""
        from auth import verify_approval_token

        self.assertFalse(verify_approval_token("SO-emp9-12345", "6553206564", "invalid.token.here"))
        print("\n✅ [TEST 9] Token sai bị từ chối đúng.")

    # ─── 10. TEST FULL FLOW: GATE → N8N → WEBHOOK → ODOO ───
    @patch("ai.get_client")
    def test_10_full_approval_flow(self, mock_client_fn):
        """Toàn bộ flow: tạo đơn lớn → gate chặn → n8n → webhook approve → Odoo."""
        import ai
        from app import approval_callback
        from fastapi import Request

        # ── BƯỚC 1: User tạo đơn > 20tr ──
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _resp([_ToolUse("create_sale_order", "t10", {"model": "sale.order"})]),
            _resp([_Text("### 📋 KẾT LUẬN\nĐơn đã chuyển xin duyệt Manager.")]),
        ]
        mock_client_fn.return_value = mock_client

        mock_mcp = MagicMock()
        mock_mcp.list_tools = AsyncMock(return_value=MagicMock(tools=[_Tool("create_sale_order")]))

        ai.clear_draft("emp10")
        ai.clear_memory("emp10")
        d = ai.get_draft("emp10")
        d.customer_id = 5
        d.customer_name = "Alice"
        d.items.append(ai.DraftItem(10, "Laptop", qty=10, unit_price=5_000_000))  # 50tr

        # Mock n8n gửi approval request
        sent_payload = {}
        def fake_send_approval_request(order_name, total, employee_name, manager_chat_id, telegram_id=None):
            sent_payload["order_name"] = order_name
            sent_payload["total"] = total
            sent_payload["manager_chat_id"] = manager_chat_id
            sent_payload["telegram_id"] = telegram_id
            return True
        ai.send_approval_request = MagicMock(side_effect=fake_send_approval_request)

        result = asyncio.run(ai.handle_message("emp10", "Tạo đơn 50tr", {
            "email": "sales@test.com", "full_name": "Sales Staff", "role_category": "sales_staff",
            "allowed_tools": ["create_sale_order"],
            "allowed_models": ["sale.order", "product.template"],
        }, mock_mcp))

        # Verify gate chặn
        self.assertIn("xin duyệt", result.lower())
        self.assertTrue(sent_payload.get("order_name", "").startswith("SO-emp10-"))
        self.assertEqual(sent_payload["total"], 50_000_000)
        self.assertEqual(sent_payload["manager_chat_id"], "6553206564")
        print(f"\n✅ [TEST 10a] Gate chặn + gửi n8n: order={sent_payload['order_name']} total={sent_payload['total']:,.0f}")

        # ── BƯỚC 2: Manager approve qua webhook ──
        order_name = sent_payload["order_name"]
        ai._odoo.create = MagicMock(return_value=777)

        payload = json.dumps({
            "action": "approve",
            "order_name": order_name,
            "telegram_id": "emp10"
        }).encode()

        sig = hmac.new(b"test-secret-123", payload, hashlib.sha256).hexdigest()

        mock_request = MagicMock(spec=Request)
        mock_request.body = AsyncMock(return_value=payload)
        mock_request.headers = {"X-Webhook-Signature": sig}
        mock_request.json = AsyncMock(return_value=json.loads(payload))

        result = asyncio.run(approval_callback(mock_request))

        # Verify đơn được tạo trên Odoo
        if isinstance(result, tuple):
            result = result[0]
        self.assertEqual(result["status"], "ok")
        ai._odoo.create.assert_called_once()
        call_args = ai._odoo.create.call_args
        self.assertEqual(call_args[0][0], "sale.order")
        self.assertEqual(call_args[0][1]["partner_id"], 5)
        self.assertEqual(len(call_args[0][1]["order_line"]), 1)
        print(f"\n✅ [TEST 10b] Webhook approve → Odoo create: {call_args[0][1]['partner_id']=}, lines={len(call_args[0][1]['order_line'])}")

        # Verify draft đã bị xóa
        self.assertNotIn("emp10", ai._drafts)
        print(f"\n✅ [TEST 10c] Draft đã được xóa sau khi approve.")

    # ─── 11. TEST APPROVE ĐƠN ĐÃ XỬ LÝ ───
    def test_11_approve_already_processed(self):
        """Approve đơn đã xử lý phải báo lỗi."""
        import ai

        ai.clear_draft("emp11")
        d = ai.get_draft("emp11")
        d.customer_id = 5
        d.customer_name = "Alice"
        d.items.append(ai.DraftItem(10, "Laptop", qty=1, unit_price=5_000_000))
        d.status = "SUBMITTED"  # Đã xử lý
        ai.register_order_ref("emp11", "SO-emp11-12345")

        ok, msg = ai.approve_order("SO-emp11-12345")
        self.assertFalse(ok)
        self.assertIn("đã xử lý", msg)
        print(f"\n✅ [TEST 11] Approve đơn đã xử lý bị từ chối: {msg[:60]}...")

    # ─── 12. TEST APPROVE ĐƠN KHÔNG TỒN TẠI ───
    def test_12_approve_nonexistent_order(self):
        """Approve đơn không tồn tại phải báo lỗi."""
        import ai

        ok, msg = ai.approve_order("SO-KHONG-TON-TAI")
        self.assertFalse(ok)
        self.assertIn("không tìm thấy", msg.lower())
        print(f"\n✅ [TEST 12] Approve đơn không tồn tại bị từ chối: {msg[:60]}...")


if __name__ == "__main__":
    unittest.main(verbosity=2)