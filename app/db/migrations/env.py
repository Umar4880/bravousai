import asyncio
import logging

from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import setting
from app.db.engine import get_app_engine
from app.domain.entities import Base
from app.utils.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

config = context.config

if setting.APP_DATABASE_URL:
    config.set_main_option("sqlalchemy.url", setting.APP_DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = get_app_engine()

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())