"""E2E Flow Test — SmartShop AI Gateway v3.0 (mô phỏng, 0 token API)."""

import os
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["ODOO_URL"] = "https://test.odoo.com"
os.environ["ODOO_DB"] = "test"
os.environ["ODOO_USERNAME"] = "admin@test.com"
os.environ["ODOO_PASSWORD"] = "pass"


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


class E2EFlowTest(unittest.TestCase):
    """Test E2E — 5 file architecture: app, ai, auth, odoo, tests."""

    def test_1_draft_order(self):
        import ai
        ai.clear_draft("u1")
        d = ai.get_draft("u1")
        d.customer_id = 5
        d.customer_name = "Alice"
        d.items.append(ai.DraftItem(10, "iPhone 15", qty=2, unit_price=1000))
        self.assertTrue(d.is_complete())
        self.assertEqual(d.total_amount, 2000)

    def test_2_draft_with_discount(self):
        import ai
        ai.clear_draft("u2")
        d = ai.get_draft("u2")
        d.customer_id = 5
        d.items.append(ai.DraftItem(20, "Samsung S24", qty=5, unit_price=28_000_000, discount=28.57))
        self.assertAlmostEqual(d.total_amount, 100_000_000, delta=5000)

    def test_3_approve_order(self):
        import ai
        from unittest.mock import MagicMock
        ai.clear_draft("emp1")
        ai._odoo.create = MagicMock(return_value=999)
        d = ai.get_draft("emp1")
        d.customer_id = 5
        d.customer_name = "Alice"
        d.items.append(ai.DraftItem(10, "iPhone", qty=1, unit_price=1000))
        ai.register_order_ref("emp1", "SO001")
        ok, msg = ai.approve_order("SO001")
        self.assertTrue(ok)
        self.assertIn("PHÊ DUYỆT", msg)
        ai._odoo.create.assert_called_once()

    def test_4_reject_order(self):
        import ai
        ai.clear_draft("emp2")
        d = ai.get_draft("emp2")
        d.customer_id = 5
        ai.register_order_ref("emp2", "SO002")
        ok, msg = ai.reject_order("SO002")
        self.assertTrue(ok)
        self.assertIn("từ chối", msg.lower())

    @patch("ai.get_client")
    def test_5_tool_loop(self, mock_client_fn):
        import ai
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _resp([_ToolUse("get_stock_quant", "t1", {"model": "stock.quant"})]),
            _resp([_Text("### 📋 KẾT LUẬN\nCòn 5 chiếc.\n### 📊 DỮ LIỆU\n| iPhone | 5 |\n### 🚀 BƯỚC TIẾP THEO")]),
        ]
        mock_client_fn.return_value = mock_client
        mock_mcp = MagicMock()
        mock_mcp.list_tools = AsyncMock(return_value=MagicMock(tools=[_Tool("get_stock_quant")]))
        mock_mcp.call_tool = AsyncMock(return_value=MagicMock(content=[_Text('{"result": [{"qty": 5}]}')]))
        ai.clear_memory("user1")
        result = asyncio.run(ai.handle_message("user1", "Kiểm tra tồn kho iPhone", {
            "email": "staff@test.com", "full_name": "Staff", "role_category": "inventory_staff",
            "allowed_tools": ["get_stock_quant", "search_records"],
            "allowed_models": ["stock.quant", "product.template"],
        }, mock_mcp))
        self.assertIn("KẾT LUẬN", result)

    @patch("ai.get_client")
    def test_6_acl_deny(self, mock_client_fn):
        import ai
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _resp([_ToolUse("search_records", "t2", {"model": "sale.order"})]),
            _resp([_Text("### 📋 KẾT LUẬN\nKhông có quyền.")]),
        ]
        mock_client_fn.return_value = mock_client
        mock_mcp = MagicMock()
        mock_mcp.list_tools = AsyncMock(return_value=MagicMock(tools=[_Tool("search_records")]))
        ai.clear_memory("user2")
        result = asyncio.run(ai.handle_message("user2", "Xem doanh số", {
            "email": "viewer@test.com", "full_name": "Viewer", "role_category": "viewer",
            "allowed_tools": ["search_records"],
            "allowed_models": ["product.template"],
        }, mock_mcp))
        self.assertIn("KẾT LUẬN", result)
        mock_mcp.call_tool.assert_not_called()

    @patch("ai.get_client")
    def test_7_approval_gate(self, mock_client_fn):
        import ai
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _resp([_ToolUse("create_sale_order", "t3", {"model": "sale.order"})]),
            _resp([_Text("### 📋 KẾT LUẬN\nĐơn đã chuyển xin duyệt.")]),
        ]
        mock_client_fn.return_value = mock_client
        mock_mcp = MagicMock()
        mock_mcp.list_tools = AsyncMock(return_value=MagicMock(tools=[_Tool("create_sale_order")]))
        ai.clear_draft("emp3")
        ai.clear_memory("emp3")
        d = ai.get_draft("emp3")
        d.customer_id = 5
        d.customer_name = "Alice"
        d.items.append(ai.DraftItem(10, "Laptop", qty=10, unit_price=5_000_000))  # 50tr
        ai.send_approval_request = MagicMock(return_value=True)
        result = asyncio.run(ai.handle_message("emp3", "Tạo đơn 50tr", {
            "email": "sales@test.com", "full_name": "Sales", "role_category": "sales_staff",
            "allowed_tools": ["create_sale_order"],
            "allowed_models": ["sale.order", "product.template"],
        }, mock_mcp))
        self.assertIn("KẾT LUẬN", result)
        mock_mcp.call_tool.assert_not_called()
        ai.send_approval_request.assert_called_once()

    def test_8_rate_limiter(self):
        from auth import rate_limit_check
        # First 3 should pass
        for i in range(3):
            ok, _ = rate_limit_check(f"test_user_{i}")
            self.assertTrue(ok)

    def test_9_idempotency(self):
        from auth import idempotency_check, idempotency_store
        is_dup, _ = idempotency_check("u9", "test message")
        self.assertFalse(is_dup)
        idempotency_store("u9", "test message", "cached response")
        is_dup, cached = idempotency_check("u9", "test message")
        self.assertTrue(is_dup)
        self.assertEqual(cached, "cached response")

    def test_10_register_clear_commands(self):
        """Test /register và /clear có phản hồi."""
        from app import handle_system_cmd, message_handler
        from unittest.mock import patch

        # Test /clear
        with patch("ai.clear_memory") as mock_clear_mem, \
             patch("ai.clear_draft") as mock_clear_draft, \
             patch("app.tg_send", new_callable=AsyncMock) as mock_send:
            asyncio.run(handle_system_cmd("123", "/clear"))
            mock_clear_mem.assert_called_once_with("123")
            mock_clear_draft.assert_called_once_with("123")
            mock_send.assert_called_once()
            self.assertIn("xoa", mock_send.call_args[0][1].lower())

        # Test /register thiếu email
        with patch("app.tg_send", new_callable=AsyncMock) as mock_send:
            asyncio.run(handle_system_cmd("123", "/register"))
            mock_send.assert_called_once()
            self.assertIn("cu phap", mock_send.call_args[0][1].lower())

        # Test /register có email
        with patch("app.request_otp", return_value=(True, "OTP sent")) as mock_otp, \
             patch("app.tg_send", new_callable=AsyncMock) as mock_send:
            asyncio.run(handle_system_cmd("123", "/register test@test.com"))
            mock_otp.assert_called_once_with("123", "test@test.com")
            mock_send.assert_called_once()


import asyncio
if __name__ == "__main__":
    unittest.main(verbosity=2)
