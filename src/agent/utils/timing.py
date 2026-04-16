import time
from functools import wraps
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

def timed_execution(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start_time
            logger.info(f"Executed {func.__name__} in {elapsed:.4f} seconds")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(f"Failed {func.__name__} after {elapsed:.4f} seconds: {str(e)}")
            raise
    return wrapper
