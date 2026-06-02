"""
API请求/响应数据模型
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class RoleType(Enum):
    """消息角色类型"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str
    content: str

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "ChatMessage":
        return cls(role="assistant", content=content)

    def to_dict(self) -> Dict:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatRequest:
    """聊天请求"""
    messages: List[ChatMessage]
    model: str = "qwen-max"
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 2048
    stream: bool = False

    def to_dict(self) -> Dict:
        return {
            "model": self.model,
            "messages": [m.to_dict() for m in self.messages],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "stream": self.stream
        }


@dataclass
class Usage:
    """Token使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatResponse:
    """聊天响应"""
    success: bool
    content: str
    model: str
    usage: Usage = field(default_factory=Usage)
    error: Optional[str] = None

    @classmethod
    def success_response(cls, content: str, model: str, usage: Dict) -> "ChatResponse":
        return cls(
            success=True,
            content=content,
            model=model,
            usage=Usage(**usage)
        )

    @classmethod
    def error_response(cls, model: str, error: str) -> "ChatResponse":
        return cls(
            success=False,
            content="",
            model=model,
            error=error
        )