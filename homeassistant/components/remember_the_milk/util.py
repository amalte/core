import asyncio


async def run_async(func):
    """Run a synchronous function in an asynchronous context."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func)
