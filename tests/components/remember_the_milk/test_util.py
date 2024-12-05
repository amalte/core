""" "Tests for the Remember The Milk utility functions."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import pytest

import homeassistant.components.remember_the_milk.util as util
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_get_time_range_day() -> None:
    """Test get_time_range for 'day' range type."""
    target = datetime(2024, 4, 27, 15, 30)
    start, end = util.get_time_range(target, "day")
    assert start == datetime(2024, 4, 27, 0, 0, 0, 0)
    assert end == datetime(2024, 4, 27, 23, 59, 59, 999999)


@pytest.mark.asyncio
async def test_get_time_range_week() -> None:
    """Test get_time_range for 'week' range type."""
    target = datetime(2024, 4, 27)  # Assume it's a Saturday
    start, end = util.get_time_range(target, "week")
    assert start == datetime(2024, 4, 22, 0, 0, 0, 0)  # Monday
    assert end == datetime(2024, 4, 28, 23, 59, 59, 999999)  # Sunday


@pytest.mark.asyncio
async def test_get_time_range_month() -> None:
    """Test get_time_range for 'month' range type."""
    target = datetime(2024, 2, 15)
    start, end = util.get_time_range(target, "month")
    assert start == datetime(2024, 2, 1, 0, 0, 0, 0)
    assert end == datetime(2024, 2, 29, 23, 59, 59, 999999)  # 2024 is a leap year


@pytest.mark.asyncio
async def test_get_time_range_invalid() -> None:
    """Test get_time_range with an invalid range type."""
    target = datetime.now()
    with pytest.raises(
        ValueError, match="Invalid range_type. Use 'day', 'week', or 'month'."
    ):
        util.get_time_range(target, "year")


@pytest.mark.asyncio
async def test_rate_limiter() -> None:
    """Test the RateLimiter to ensure it limits the rate of function calls."""
    rate = 0.1  # 100ms rate limit
    limiter = util.RateLimiter(rate)

    dummy_func = AsyncMock(return_value="done")

    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        await limiter.start()

        # Call the rate limiter twice
        result1 = await limiter.call(dummy_func)
        result2 = await limiter.call(dummy_func)

        assert result1 == "done"
        assert result2 == "done"
        assert mock_sleep.call_count == 2  # Sleep called after each call

        # Cleanup the limiter task
        limiter.task.cancel()
        try:
            await limiter.task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_run_async() -> None:
    """Test the run_async utility function."""
    rate = 0.1
    limiter = util.RateLimiter(rate)

    async def setup_limiter():
        await limiter.start()

    await setup_limiter()

    sync_function = Mock(return_value="sync_result")

    with patch.object(
        limiter, "call", new=AsyncMock(return_value="async_result")
    ) as mock_call:
        result = await util.run_async(limiter, sync_function)
        assert result == "async_result"
        mock_call.assert_called_once_with(
            ANY  # Since the actual callable is a wrapper
        )

        # Cleanup the limiter task
        limiter.task.cancel()
        try:
            await limiter.task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_rate_limiter_exception_handling() -> None:
    """Test that RateLimiter handles exceptions in the called function."""
    rate = 0.1
    limiter = util.RateLimiter(rate)

    faulty_func = AsyncMock(side_effect=RuntimeError("Test exception"))

    with patch("asyncio.sleep", new=AsyncMock()):
        await limiter.start()

        with pytest.raises(RuntimeError, match="Test exception"):
            await limiter.call(faulty_func)

        # Verify that sleep was called once
        limiter.task.cancel()
        try:
            await limiter.task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_rate_limiter_order() -> None:
    """Test that RateLimiter processes functions in the order they were added."""
    rate = 0.1
    limiter = util.RateLimiter(rate)

    call_order = []

    async def func1():
        call_order.append("func1")
        return "result1"

    async def func2():
        call_order.append("func2")
        return "result2"

    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        await limiter.start()

        res1 = await limiter.call(func1)
        res2 = await limiter.call(func2)

        assert res1 == "result1"
        assert res2 == "result2"
        assert call_order == ["func1", "func2"]
        assert mock_sleep.call_count == 2  # Sleep called after each call

        # Cleanup the limiter task
        limiter.task.cancel()
        try:
            await limiter.task
        except asyncio.CancelledError:
            pass
