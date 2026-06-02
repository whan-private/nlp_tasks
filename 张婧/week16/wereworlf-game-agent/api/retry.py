"""
API请求重试机制
实现自动重试、指数退避
"""

import time
import logging
from functools import wraps
from typing import Callable, Any, List, Type, Union

logger = logging.getLogger(__name__)


class RetryConfig:
    """重试配置"""

    def __init__(
            self,
            max_retries: int = 3,
            base_delay: float = 1.0,
            max_delay: float = 10.0,
            backoff_factor: float = 2.0,
            retry_on_status: List[int] = None,
            retry_on_exceptions: List[Type[Exception]] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retry_on_status = retry_on_status or [429, 500, 502, 503, 504]
        self.retry_on_exceptions = retry_on_exceptions or [Exception]


def retry(config: RetryConfig = None):
    """重试装饰器"""

    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # 检查结果是否需要重试
                    if hasattr(result, 'success') and not result.success:
                        if attempt < config.max_retries:
                            delay = min(
                                config.base_delay * (config.backoff_factor ** attempt),
                                config.max_delay
                            )
                            logger.warning(
                                f"请求失败 (attempt {attempt + 1}/{config.max_retries + 1})，{delay:.2f}秒后重试")
                            time.sleep(delay)
                            continue

                    return result

                except Exception as e:
                    last_exception = e

                    if attempt < config.max_retries:
                        # 检查是否需要重试
                        should_retry = any(
                            isinstance(e, exc_type) for exc_type in config.retry_on_exceptions
                        )

                        if should_retry:
                            delay = min(
                                config.base_delay * (config.backoff_factor ** attempt),
                                config.max_delay
                            )
                            logger.warning(
                                f"请求异常: {e}，{delay:.2f}秒后重试 (attempt {attempt + 1}/{config.max_retries + 1})")
                            time.sleep(delay)
                            continue

                    raise

            # 所有重试都失败
            raise last_exception

        return wrapper

    return decorator


class APIRetry:
    """API重试工具类"""

    @staticmethod
    def async_retry(func: Callable, max_retries: int = 3):
        """异步重试"""

        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = min(2 ** attempt, 10)
                    logger.warning(f"异步请求失败，{delay}秒后重试: {e}")
                    await asyncio.sleep(delay)
            return None

        return wrapper