"""
E2E Flow Test — SmartShop Odoo 19 AI Gateway (mô phỏng, không tốn API token).
Test toàn bộ luồng nghiệp vụ: Auth → Intent → Skill → Tool Loop → Duyệt đơn.
"""

import os
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

os.environ["ANTHROPIC_API_KEY"] = "test-key"


class _MCPTool:
    """Giả lập tool MCP."""

    def __init__(self, name, desc="desc"):
        self.name = name
        self.description = desc
        self.input_schema = {"type": "object", "properties": {}}


class _ToolUse:
    def __init__(self, name, tool_id, args):
        self.name = name
        self.id = tool_id
        self.input = args
        self.type = "tool_use"


class _TextBlock:
    def __init__(self, text):
        self.text = text
        self.type = "text"


def _make_response(content_blocks):
    resp = MagicMock()
    resp.content = content_blocks
    return resp


class E2EFlowTest(unittest.TestCase):
    """Test E2E flow sử dụng mock hoàn toàn (0 token API)."""

    @classmethod
    def setUpClass(cls):
        os.environ["ODOO_URL"] = "https://test.odoo.com"
        os.environ["ODOO_DB"] = "test"
        os.environ["ODOO_USERNAME"] = "admin@test.com"
        os.environ["ODOO_PASSWORD"] = "pass"

    def test_1_intent_router(self):
        from orchestrator.intent_router import IntentRouter
        router = IntentRouter()
        self.assertEqual(router.route_intent("Kiểm tra tồn kho iPhone"), "INVENTORY_LOOKUP")
        self.assertEqual(router.route_intent("Tạo đơn hàng cho Alice"), "SALE_ORDER_CREATE")
        self.assertEqual(router.route_intent("Xin chào"), "GENERAL")

    def test_2_skill_loader(self):
        from orchestrator.skill_loader import SkillLoader
        loader = SkillLoader()
        tools = loader.get_effective_tools("INVENTORY_LOOKUP", ["get_stock_quant", "search_records"])
        self.assertIn("get_stock_quant", tools)
        self.assertNotIn("create_sale_order", tools)

    def test_3_draft_order_flow(self):
        from orchestrator.draft_order_service import OrderDraftStateService
        svc = OrderDraftStateService()
        svc.set_customer("u1", 5, "Alice")
        svc.add_item("u1", 10, "iPhone 15", qty=2, unit_price=1000)
        draft = svc.get_draft("u1")
        self.assertTrue(draft.is_complete())
        self.assertEqual(draft.total_amount, 2000)

    def test_4_fulfillment_approve_reject(self):
        """Manager duyệt đơn -> tạo sale.order; reject -> xóa draft."""
        from orchestrator.order_fulfillment_service import OrderFulfillmentService
        from orchestrator.draft_order_service import OrderDraftStateService

        draft_svc = OrderDraftStateService()
        fulfillment = OrderFulfillmentService(draft_service=draft_svc)
        fulfillment.odoo_client.create = MagicMock(return_value=999)

        # Nhân viên tạo draft
        draft_svc.set_customer("emp1", 5, "Alice")
        draft_svc.add_item("emp1", 10, "iPhone 15", qty=1, unit_price=1000)
        fulfillment.register_order_reference("emp1", "SO001")

        # Manager approve
        ok, msg = fulfillment.approve_order("SO001")
        self.assertTrue(ok)
        self.assertIn("PHÊ DUYỆT", msg)
        fulfillment.odoo_client.create.assert_called_once()
        # Draft bị xóa sau khi approve
        self.assertEqual(draft_svc.get_draft("emp1").customer_id, None)

    def test_5_fulfillment_reject(self):
        from orchestrator.order_fulfillment_service import OrderFulfillmentService
        from orchestrator.draft_order_service import OrderDraftStateService
        draft_svc = OrderDraftStateService()
        fulfillment = OrderFulfillmentService(draft_service=draft_svc)
        draft_svc.set_customer("emp2", 5, "Alice")
        fulfillment.register_order_reference("emp2", "SO002")
        ok, msg = fulfillment.reject_order("SO002")
        self.assertTrue(ok)
        self.assertIn("từ chối", msg.lower())

    @patch("orchestrator.claude_adapter.get_client")
    def test_6_claude_adapter_tool_loop(self, mock_get_client):
        """Mô phỏng đầy đủ: Claude gọi tool → MCP trả kết quả → response."""
        from orchestrator.claude_adapter import ClaudeAdapter

        # Giả lập Claude client trả về: turn 1 = tool_use, turn 2 = text
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _make_response([
                _ToolUse("get_stock_quant", "toolu_1", {"model": "stock.quant", "domain": [["product_id", "=", 10]]})
            ]),
            _make_response([
                _TextBlock("### 📋 KẾT LUẬN\nCòn 5 chiếc.\n### 📊 DỮ LIỆU THỰC TẾ\n| Sản phẩm | Tồn |\n| iPhone | 5 |\n### 🚀 BƯỚC TIẾP THEO")
            ]),
        ]
        mock_get_client.return_value = mock_client

        # Giả lập MCP session
        mock_mcp = MagicMock()
        mock_mcp.list_tools = AsyncMock(return_value=MagicMock(tools=[_MCPTool("get_stock_quant"), _MCPTool("search_records")]))
        mock_mcp.call_tool = AsyncMock(return_value=MagicMock(
            content=[_TextBlock('{"result": [{"product_id": 10, "quantity": 5}]}')]
        ))

        adapter = ClaudeAdapter()
        user_info = {
            "email": "staff@test.com",
            "full_name": "Staff",
            "role_category": "inventory_staff",
            "allowed_tools": ["get_stock_quant", "search_records"],
            "allowed_models": ["stock.quant", "product.template", "product.product"],
        }

        import asyncio
        result = asyncio.run(adapter.handle_message("user1", "Kiểm tra tồn kho iPhone", user_info, mock_mcp))
        self.assertIn("KẾT LUẬN", result)

    @patch("orchestrator.claude_adapter.get_client")
    def test_7_claude_adapter_acl_deny(self, mock_get_client):
        """Model ACL enforcement: user không có quyền → tool bị chặn."""
        from orchestrator.claude_adapter import ClaudeAdapter

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _make_response([
                _ToolUse("search_records", "toolu_2", {"model": "sale.order", "domain": []})
            ]),
            _make_response([
                _TextBlock("### 📋 KẾT LUẬN\nBạn không có quyền.")
            ]),
        ]
        mock_get_client.return_value = mock_client

        mock_mcp = MagicMock()
        mock_mcp.list_tools = AsyncMock(return_value=MagicMock(tools=[_MCPTool("search_records")]))

        adapter = ClaudeAdapter()
        user_info = {
            "email": "viewer@test.com",
            "full_name": "Viewer",
            "role_category": "viewer",
            "allowed_tools": ["search_records"],
            "allowed_models": ["product.template"],  # KHÔNG có sale.order
        }

        import asyncio
        result = asyncio.run(adapter.handle_message("user2", "Xem sale.order", user_info, mock_mcp))
        self.assertIn("KẾT LUẬN", result)
        # Đảm bảo call_tool KHÔNG được gọi cho sale.order (bị ACL chặn)
        mock_mcp.call_tool.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)