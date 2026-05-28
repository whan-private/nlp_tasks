"""
API请求限流器
防止超出调用频率限制
"""

import time
from threading import Lock
from functools import wraps
from typing import Dict, Optional


class RateLimiter:
    """
    令牌桶限流器
    """

    def __init__(self, rate: float = 10, capacity: int = 20):
        """
        初始化限流器

        Args:
            rate: 每秒添加的令牌数
            capacity: 桶容量
        """
        self.rate = rate  # 令牌添加速率（个/秒）
        self.capacity = capacity  # 桶容量
        self.tokens = capacity  # 当前令牌数
        self.last_refill = time.time()
        self.lock = Lock()

    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.rate

        if new_tokens > 0:
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_refill = now

    def acquire(self, tokens: int = 1) -> bool:
        """
        获取令牌

        Args:
            tokens: 需要的令牌数

        Returns:
            是否获取成功
        """
        with self.lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_and_acquire(self, tokens: int = 1, timeout: float = None) -> bool:
        """
        等待并获取令牌

        Args:
            tokens: 需要的令牌数
            timeout: 超时时间（秒）

        Returns:
            是否获取成功
        """
        start_time = time.time()

        while not self.acquire(tokens):
            if timeout and (time.time() - start_time) > timeout:
                return False
            time.sleep(0.1)

        return True


class RateLimiterManager:
    """限流器管理器"""

    _limiters: Dict[str, RateLimiter] = {}

    @classmethod
    def get_limiter(cls, name: str, rate: float = 10, capacity: int = 20) -> RateLimiter:
        """获取或创建限流器"""
        if name not in cls._limiters:
            cls._limiters[name] = RateLimiter(rate, capacity)
        return cls._limiters[name]

    @classmethod
    def acquire(cls, name: str, tokens: int = 1) -> bool:
        """获取令牌"""
        limiter = cls.get_limiter(name)
        return limiter.acquire(tokens)