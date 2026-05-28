"""
千问模型API客户端
封装与阿里云DashScope的交互
"""

import os
import json
from typing import List, Dict, Optional, Any
from openai import OpenAI

from .base import BaseLLMClient, Message, LLMResponse


class QwenClient(BaseLLMClient):
    """千问模型客户端"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化千问客户端

        Args:
            config: 配置字典，包含 url, api_key, model
        """
        self.url = config.get("url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.api_key = config.get("api_key", os.environ.get("QWEN_API_KEY", ""))
        self.model = config.get("model", "qwen-max")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.url
        )

        self.default_params = {
            "temperature": config.get("temperature", 0.7),
            "top_p": config.get("top_p", 0.9),
            "max_tokens": config.get("max_tokens", 2048)
        }

    def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """发送对话请求"""
        try:
            # 转换消息格式
            api_messages = [{"role": m.role, "content": m.content} for m in messages]

            # 合并参数
            params = {**self.default_params, **kwargs}

            # 调用API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=params.get("temperature"),
                top_p=params.get("top_p"),
                max_tokens=params.get("max_tokens")
            )

            return LLMResponse(
                success=True,
                content=response.choices[0].message.content,
                model=self.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )

        except Exception as e:
            return LLMResponse(
                success=False,
                content="",
                model=self.model,
                usage={},
                error=str(e)
            )

    def chat_simple(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """简化的对话接口"""
        messages = []
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))
        messages.append(Message(role="user", content=prompt))

        response = self.chat(messages, **kwargs)
        return response.content if response.success else ""

    def get_model_name(self) -> str:
        return self.model