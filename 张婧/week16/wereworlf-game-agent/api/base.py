"""
API模块基类
定义所有LLM客户端的统一接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class Message:
    """消息结构"""
    role: str  # 'system', 'user', 'assistant'
    content: str


@dataclass
class LLMResponse:
    """LLM响应结构"""
    success: bool
    content: str
    model: str
    usage: Dict[str, int]  # token使用情况
    error: Optional[str] = None


class BaseLLMClient(ABC):
    """LLM客户端抽象基类"""

    @abstractmethod
    def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """发送对话请求"""
        pass

    @abstractmethod
    def chat_simple(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """简化的对话接口"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass