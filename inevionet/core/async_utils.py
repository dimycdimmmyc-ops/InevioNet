"""InevioNet Async Utils."""
import asyncio
import time
import random
import threading
from typing import Callable, Any, List, Optional, TypeVar, Awaitable
from functools import wraps

from .logger import get_logger

logger = get_logger("inevionet.core.async_utils")

T = TypeVar("T")


def with_retry(max_retries=3, base_delay=0.5, max_delay=10.0,
               exponential=True, jitter=True, exceptions=(Exception,)):
    """Decorator for retry with exponential backoff."""
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
                        break
                    if exponential:
                        delay = min(max_delay, base_delay * (2 ** attempt))
                    else:
                        delay = base_delay
                    if jitter:
                        delay *= random.uniform(0.5, 1.5)
                    time.sleep(delay)
            raise last_exception

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt >= max_retries:
                        break
                    if exponential:
                        delay = min(max_delay, base_delay * (2 ** attempt))
                    else:
                        delay = base_delay
                    if jitter:
                        delay *= random.uniform(0.5, 1.5)
                    await asyncio.sleep(delay)
            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


async def parallel_execute(tasks, max_concurrent=10, timeout=None):
    """Parallel execution with concurrency limit."""
    semaphore = asyncio.Semaphore(max_concurrent)
    results = [None] * len(tasks)

    async def run_with_semaphore(index, task):
        async with semaphore:
            try:
                if timeout:
                    result = await asyncio.wait_for(task(), timeout=timeout)
                else:
                    result = await task()
                results[index] = result
            except Exception as e:
                results[index] = e

    await asyncio.gather(*[run_with_semaphore(i, t) for i, t in enumerate(tasks)])
    return results


def parallel_run(funcs, max_workers=10):
    """Parallel execution of sync functions via ThreadPool."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = [None] * len(funcs)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(func): i for i, func in enumerate(funcs)}
        for future in as_completed(futures):
            i = futures[future]
            try:
                results[i] = future.result()
            except Exception as e:
                results[i] = e
    return results


async def batch_process(items, processor, batch_size=100, max_concurrent=10):
    """Batch processing."""
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        tasks = [lambda item=item: processor(item) for item in batch]
        batch_results = await parallel_execute(tasks, max_concurrent=max_concurrent)
        results.extend(batch_results)
    return results


class Debouncer:
    """Debounce for async calls."""

    def __init__(self, delay=0.5):
        self.delay = delay
        self._task = None

    async def call(self, func, *args, **kwargs):
        if self._task:
            self._task.cancel()

        async def delayed():
            await asyncio.sleep(self.delay)
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)

        self._task = asyncio.create_task(delayed())

    def cancel(self):
        if self._task:
            self._task.cancel()
            self._task = None


class Throttle:
    """Throttle for async calls."""

    def __init__(self, rate=10.0):
        self.min_interval = 1.0 / rate
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_call = time.monotonic()


if __name__ == "__main__":
    print("Testing async_utils...")

    attempt_count = [0]

    @with_retry(max_retries=3, base_delay=0.01)
    def unstable():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ValueError("Not yet")
        return "Success"

    result = unstable()
    print(f"Retry result: {result}, attempts: {attempt_count[0]}")

    async def test_parallel():
        async def task(n):
            await asyncio.sleep(0.01)
            return n * 2
        tasks = [lambda n=i: task(n) for i in range(5)]
        return await parallel_execute(tasks, max_concurrent=3)

    results = asyncio.run(test_parallel())
    print(f"Parallel results: {results}")

    def compute(n):
        time.sleep(0.01)
        return n ** 2

    funcs = [lambda n=i: compute(n) for i in range(5)]
    results = parallel_run(funcs, max_workers=5)
    print(f"ThreadPool results: {results}")

    print("Async utils module OK")
