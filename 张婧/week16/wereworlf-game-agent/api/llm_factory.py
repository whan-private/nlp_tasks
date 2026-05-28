"""
LLM客户端工厂
统一管理不同模型的创建和获取
"""

from typing import Dict, Any, Optional
from .base import BaseLLMClient
from .qwen_client import QwenClient


class LLMFactory:
    """LLM客户端工厂"""

    _clients: Dict[str, BaseLLMClient] = {}

    @classmethod
    def create_client(cls, provider: str, config: Dict[str, Any]) -> BaseLLMClient:
        """
        创建LLM客户端

        Args:
            provider: 提供商名称 ('qwen', 'openai', 'deepseek')
            config: 配置字典

        Returns:
            LLM客户端实例
        """
        if provider == "qwen":
            client = QwenClient(config)
        elif provider == "openai":
            # from .openai_client import OpenAIClient
            # client = OpenAIClient(config)
            raise NotImplementedError("OpenAI客户端待实现")
        elif provider == "deepseek":
            # from .deepseek_client import DeepSeekClient
            # client = DeepSeekClient(config)
            raise NotImplementedError("DeepSeek客户端待实现")
        else:
            raise ValueError(f"不支持的模型提供商: {provider}")

        cls._clients[provider] = client
        return client

    @classmethod
    def get_client(cls, provider: str) -> Optional[BaseLLMClient]:
        """获取已创建的客户端"""
        return cls._clients.get(provider)

    @classmethod
    def clear(cls):
        """清除所有客户端"""
        cls._clients.clear()