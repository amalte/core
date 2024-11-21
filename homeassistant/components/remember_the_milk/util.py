"""Utility functions for Remember The Milk integration."""

import asyncio
from datetime import datetime, timedelta


def get_time_range(target_datetime: datetime, range_type: str):
    """Get the start and end time of a specific range (day, week, or month)."""
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


async def run_async(func):
    """Run a synchronous function in an asynchronous context."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func)
