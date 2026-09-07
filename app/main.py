from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import asyncio
import sys

# Windows: psycopg requires SelectorEventLoop, not ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.api.middleware import RequestLoggingMiddleware
from app.ai.tools.deep_research_tool import deep_research_tool
from app.core.config import reload_setting, setting
from app.utils.logging import setup_logging
from app.db.engine import (
    get_checkpoint_pool,
    close_checkpoint_pool_if_initialized,
    dispose_app_engine_if_initialized,
    dispose_checkpoint_engine_if_initialized,
)
from app.core.llm_provider import get_llm
from app.services import (
    ChatService,
    AuthService
)

# App logger
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    reload_setting()
    logger.info("Startup_begin....")

    # setup agent params
    pool = get_checkpoint_pool()
    await pool.open()

    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    llm = get_llm(agent_name="main")
    tools = [deep_research_tool]

    app.state.chat_service = ChatService(
        llm=llm,
        tools=tools,
        checkpointer=checkpointer,
    )
    logger.info("Agent setup complete.")

    # Redis setup
    app.state.redis = aioredis.from_url(
        setting.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    logger.info("Redis connection setup complete.")
    yield

    logger.info("shutdown_begin")
    redis_client = getattr(app.state, "redis", None)
    if redis_client is not None:
        await redis_client.aclose()
    await close_checkpoint_pool_if_initialized()
    await dispose_app_engine_if_initialized()
    await dispose_checkpoint_engine_if_initialized()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Bravous MultiAgent API",
        version="1.0.0",
        docs_url="/docs" if setting.DEBUG else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # ── Middleware — outermost first ────────────────────────────────
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in setting.ALLOWED_ORIGINS.split(",") if o.strip()] or ["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # ── Routes ──────────────────────────────────────────────────────
    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_app()
