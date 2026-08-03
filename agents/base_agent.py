"""
Base Agent — Abstract Interface cho tất cả SmartShop Workflow Agents.
Mọi Agent đều kế thừa BaseAgent và implement method `run()`.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class AgentResult:
    """
    Kết quả trả về chuẩn từ mọi Agent.
    success: True nếu agent hoàn thành nhiệm vụ.
    response: Nội dung phản hồi gửi đến user.
    needs_approval: True nếu cần Human-in-the-Loop (HITL) phê duyệt.
    approval_context: Context cho nút bấm approve/reject.
    next_agent: Tên agent tiếp theo cần chạy (None nếu pipeline kết thúc).
    metadata: Dict chứa dữ liệu tạm thời giữa các agent.
    """
    success: bool
    response: str
    needs_approval: bool = False
    approval_context: dict = field(default_factory=dict)
    next_agent: str | None = None
    metadata: dict = field(default_factory=dict)
    latency_ms: float = 0.0
    agent_name: str = ""


class BaseAgent(ABC):
    """
    Abstract Base Agent cho SmartShop Multi-Agent Pipeline.
    
    Workflow: Recommendation → Validation → Fulfillment
    Mỗi agent nhận context từ agent trước (metadata chaining).
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def run(
        self,
        user_id: str,
        user_text: str,
        user_info: dict,
        mcp_session: Any,
        context: dict | None = None,
    ) -> AgentResult:
        """
        Thực thi agent logic.

        Args:
            user_id: Telegram/channel user ID
            user_text: Nội dung tin nhắn của user
            user_info: Dict chứa thông tin user (role, email, full_name)
            mcp_session: MCP ClientSession đang active
            context: Context chuyển tiếp từ agent trước (metadata chaining)

        Returns:
            AgentResult với response và routing decision
        """
        ...

    async def execute(
        self,
        user_id: str,
        user_text: str,
        user_info: dict,
        mcp_session: Any,
        context: dict | None = None,
    ) -> AgentResult:
        """
        Wrapper thực thi agent với đo latency tự động.
        Gọi method này thay vì `run()` trực tiếp.
        """
        start = time.perf_counter()
        result = await self.run(user_id, user_text, user_info, mcp_session, context)
        result.latency_ms = (time.perf_counter() - start) * 1000
        result.agent_name = self.name
        return result

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}'>"
