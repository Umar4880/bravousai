import functools
import logging
import httpx

from inspect import iscoroutinefunction
from tenacity import(
    retry, 
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential
)

logger = logging.getLogger(__name__)

def log_execution(func):
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception("Error in %s", func.__qualname__, str(e))

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.exception("Error in %s", func.__qualname__, str(e))

    return async_wrapper if iscoroutinefunction(func) else sync_wrapper


def retry_it(
    attempts: int = 5,
    multiplier: int = 1,
    max_wait: int = 60, 
    retry_on: tuple = (
        httpx.ConnectError, 
        httpx.TimeoutException,
        httpx.HTTPStatusError,
        
    )
):
    """
    Enterprise-grade retry decorator factory for AI services.
    """
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_random_exponential(multiplier=multiplier, max=max_wait),
        retry=retry_if_exception_type(retry_on),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )