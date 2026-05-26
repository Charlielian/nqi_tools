# -*- coding: utf-8 -*-
"""
重试工具模块
提供指数退避重试机制
"""

import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """重试耗尽异常"""
    pass


def exponential_backoff(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
    exceptions=(Exception,)
):
    """指数退避重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        exponential_base: 指数基数
        jitter: 是否添加随机抖动
        exceptions: 需要重试的异常类型元组

    Returns:
        装饰器函数

    Example:
        @exponential_backoff(max_retries=3, base_delay=1.0)
        def fetch_data():
            return requests.get(url)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        logger.error("[重试] 已达到最大重试次数 %d", max_retries)
                        raise RetryError(f"重试耗尽: {e}") from e

                    # 计算延迟时间
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    # 添加随机抖动（±25%）
                    if jitter:
                        import random
                        jitter_range = delay * 0.25
                        delay = delay + random.uniform(-jitter_range, jitter_range)
                        delay = max(0.1, delay)  # 确保延迟为正

                    logger.warning("[重试] 第 %d/%d 次失败: %s, %.1f秒后重试...",
                                 attempt + 1, max_retries, str(e)[:50], delay)
                    time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


def retry_with_backoff(func, max_retries=3, base_delay=1.0, max_delay=60.0,
                      exponential_base=2.0, jitter=True, exceptions=(Exception,)):
    """带指数退避的函数重试（可调用形式）

    Args:
        func: 要重试的函数
        max_retries: 最大重试次数
        base_delay: 基础延迟时间
        max_delay: 最大延迟时间
        exponential_base: 指数基数
        jitter: 是否添加随机抖动
        exceptions: 捕获的异常类型

    Returns:
        函数返回值

    Raises:
        RetryError: 当所有重试都失败时抛出

    Example:
        result = retry_with_backoff(
            lambda: requests.get(url),
            max_retries=3,
            base_delay=2.0
        )
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as e:
            last_exception = e

            if attempt >= max_retries:
                logger.error("[重试] 已达到最大重试次数 %d", max_retries)
                raise RetryError(f"重试耗尽: {e}") from e

            delay = min(base_delay * (exponential_base ** attempt), max_delay)

            if jitter:
                import random
                jitter_range = delay * 0.25
                delay = delay + random.uniform(-jitter_range, jitter_range)
                delay = max(0.1, delay)

            logger.warning("[重试] 第 %d/%d 次失败: %s, %.1f秒后重试...",
                         attempt + 1, max_retries, str(e)[:50], delay)
            time.sleep(delay)

    raise last_exception
