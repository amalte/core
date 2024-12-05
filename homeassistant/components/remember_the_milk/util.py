"""Utility functions for Remember The Milk integration."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta


def get_time_range(target_datetime: datetime, range_type: str):
    """Get the start and end time of a specific range (day, week, or month).

    Args:
        target_datetime (datetime): The reference datetime.
        range_type (str): The range type, one of 'day', 'week', or 'month'.

    Returns:
        tuple[datetime, datetime]: A tuple containing the start and end times of the range.

    Raises:
        ValueError: If an invalid range_type is provided.

    """
    if range_type == "day":
        start_time = target_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1) - timedelta(microseconds=1)
    elif range_type == "week":
        start_time = target_datetime - timedelta(days=target_datetime.weekday())
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=7) - timedelta(microseconds=1)
    elif range_type == "month":
        start_time = target_datetime.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if target_datetime.month == 12:
            next_month = target_datetime.replace(
                year=target_datetime.year + 1, month=1, day=1
            )
        else:
            next_month = target_datetime.replace(month=target_datetime.month + 1, day=1)
        end_time = next_month - timedelta(microseconds=1)
    else:
        raise ValueError("Invalid range_type. Use 'day', 'week', or 'month'.")

    return start_time, end_time


class RateLimiter:
    """A rate limiter to manage the rate of function calls."""

    def __init__(self, rate: float) -> None:
        """Initialize the rate limiter.

        Args:
            rate (float): The interval between function calls in seconds.

        """
        self.rate = rate
        self.queue = asyncio.Queue()
        self.task = None

    async def start(self):
        """Start the worker task for processing the queue."""
        self.task = asyncio.create_task(self._worker())

    async def _worker(self):
        """Worker to process queued functions at a limited rate."""
        while True:
            func, future = await self.queue.get()
            try:
                result = await func()
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            await asyncio.sleep(self.rate)
            self.queue.task_done()

    async def call(self, func: Callable):
        """Queue a function for execution.

        Args:
            func (Callable): The function to be called.

        Returns:
            The result of the function call.

        """
        future = asyncio.get_event_loop().create_future()
        await self.queue.put((func, future))
        return await future


async def run_async(rate_limiter: RateLimiter, func: Callable):
    """Run a synchronous function in an asynchronous context.

    Args:
        rate_limiter (RateLimiter): An instance of the RateLimiter class.
        func (Callable): The synchronous function to run.

    Returns:
        The result of the synchronous function executed asynchronously.

    """

    async def wrapper():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func)

    return await rate_limiter.call(wrapper)
