import asyncio
import sys


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        import uvicorn.loops.asyncio as uvicorn_asyncio

        def _selector_asyncio_loop_factory(use_subprocess: bool = False):
            return asyncio.SelectorEventLoop

        uvicorn_asyncio.asyncio_loop_factory = _selector_asyncio_loop_factory
    except Exception:
        pass