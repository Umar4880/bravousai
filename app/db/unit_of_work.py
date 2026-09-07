# db/unit_of_work.py

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from app.db.engine import get_session_factory
from app.domain.repositories.conversation import ConversationRepository
from app.domain.repositories.message import MessageRepository
from app.domain.repositories.artifact import ArtifactRepository
from app.domain.repositories.workflow_record import WorkflowRecordRepository
from app.domain.repositories.user import UserRepository
from app.domain.repositories.research_trace import ResearchTraceRepository
from app.domain.repositories.project import ProjectRepository

logger = logging.getLogger(__name__)


class UnitOfWork:
    """
    Single transaction boundary for all DB operations.

    All repositories share one session — atomicity guaranteed.
    If anything fails, everything rolls back. Nothing is partial.

    Usage:
        async with UnitOfWork() as uow:
            conv = await uow.conversations.create(user_id="u_123")
            await uow.messages.save(conv.id, user_id="u_123", role="user", content="hello")
            await uow.commit()
            # Both saved atomically — or both rolled back on failure
    """

    def __init__(self) -> None:
        self._factory = get_session_factory()
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "UnitOfWork":
        self._session = self._factory()

        self.users = UserRepository(self._session)
        self.projects = ProjectRepository(self._session)
        self.conversations = ConversationRepository(self._session)
        self.messages = MessageRepository(self._session)
        self.artifacts = ArtifactRepository(self._session)
        self.workflow_records = WorkflowRecordRepository(self._session)
        self.research_traces = ResearchTraceRepository(self._session)

        logger.debug("UnitOfWork | session opened")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            if exc_type is not None:
                await self.rollback()
                logger.warning(
                    "UnitOfWork | rolled back due to exception | %s: %s",
                    exc_type.__name__,
                    exc_val,
                )
        finally:
            await self._session.close()
            logger.debug("UnitOfWork | session closed")

    async def commit(self) -> None:
        try:
            await self._session.commit()
            logger.debug("UnitOfWork | committed")

        except SQLAlchemyError:
            logger.exception("UnitOfWork | commit failed — rolling back")
            await self.rollback()
            raise

    async def rollback(self) -> None:
        try:
            await self._session.rollback()
            logger.debug("UnitOfWork | rolled back")
        except SQLAlchemyError:
            logger.exception("UnitOfWork | rollback failed")
            raise
