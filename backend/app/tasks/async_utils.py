"""Shared async utilities for Celery tasks.

Provides a consistent way to run async coroutines from synchronous Celery tasks
without disposing the database engine after every task execution.
"""

import asyncio


def run_async(coro):
    """Run an async coroutine from a synchronous Celery task.

    Creates a new event loop for the task but does NOT dispose the
    SQLAlchemy engine afterwards, keeping the connection pool alive
    across tasks within the same worker process.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)
