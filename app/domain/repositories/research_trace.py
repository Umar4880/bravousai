import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.domain.entities import Conversation, FetchedUrl, Project, ResearchPlanRecord
from app.domain.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ResearchTraceRepository(BaseRepository):
    async def _ensure_owned_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
    ) -> None:
        stmt = select(Conversation.id).where(
            Conversation.id == conversation_id,
            Conversation.project_id.in_(
                select(Project.id).where(Project.user_id == user_id)
            ),
        )
        result = await self._s.execute(stmt)

        if result.scalar_one_or_none() is None:
            raise PermissionError(
                "Conversation not found or does not belong to authenticated user."
            )

    async def create_research_plan(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        plan_json: dict[str, Any],
        synthesized_content: Optional[str] = None,
        workflow_record_id: Optional[uuid.UUID] = None,
        message_id: Optional[uuid.UUID] = None,
    ) -> ResearchPlanRecord:
        try:
            await self._ensure_owned_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
            )

            record = ResearchPlanRecord(
                conversation_id=conversation_id,
                workflow_record_id=workflow_record_id,
                message_id=message_id,
                topic=str(plan_json.get("topic") or "Research plan")[:256],
                research_depth=str(plan_json.get("research_depth") or "normal"),
                plan_json=plan_json,
                synthesized_content=synthesized_content,
            )
            self._s.add(record)
            await self._s.flush()
            return record

        except SQLAlchemyError:
            logger.exception(
                "ResearchTraceRepository | create_research_plan failed | "
                "conversation_id=%s",
                conversation_id,
            )
            raise

    async def create_fetched_url(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        query: str,
        url: str,
        title: Optional[str] = None,
        source: Optional[str] = None,
        published_date: Optional[str] = None,
        snippet: Optional[str] = None,
        fetched_content: Optional[str] = None,
        relevance: Optional[str] = None,
        workflow_record_id: Optional[uuid.UUID] = None,
        research_plan_id: Optional[uuid.UUID] = None,
        message_id: Optional[uuid.UUID] = None,
    ) -> FetchedUrl:
        try:
            await self._ensure_owned_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
            )

            record = FetchedUrl(
                conversation_id=conversation_id,
                workflow_record_id=workflow_record_id,
                research_plan_id=research_plan_id,
                message_id=message_id,
                query=query,
                title=title,
                url=url,
                source=source,
                published_date=published_date,
                snippet=snippet,
                fetched_content=fetched_content,
                relevance=relevance,
            )
            self._s.add(record)
            await self._s.flush()
            return record

        except SQLAlchemyError:
            logger.exception(
                "ResearchTraceRepository | create_fetched_url failed | url=%s",
                url,
            )
            raise

    async def get_latest_research_plan(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
    ) -> Optional[ResearchPlanRecord]:
        try:
            stmt = (
                select(ResearchPlanRecord)
                .join(Conversation)
                .where(
                    ResearchPlanRecord.conversation_id == conversation_id,
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    ),
                )
                .order_by(ResearchPlanRecord.created_at.desc())
                .limit(1)
            )
            result = await self._s.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception(
                "ResearchTraceRepository | get_latest_research_plan failed | "
                "conversation_id=%s",
                conversation_id,
            )
            raise

    async def get_research_plan_for_message(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        message_id: uuid.UUID,
    ) -> Optional[ResearchPlanRecord]:
        try:
            stmt = (
                select(ResearchPlanRecord)
                .join(Conversation)
                .where(
                    ResearchPlanRecord.conversation_id == conversation_id,
                    ResearchPlanRecord.message_id == message_id,
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    ),
                )
                .order_by(ResearchPlanRecord.created_at.desc())
                .limit(1)
            )
            result = await self._s.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception(
                "ResearchTraceRepository | get_research_plan_for_message failed | "
                "message_id=%s",
                message_id,
            )
            raise

    async def list_fetched_urls(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        research_plan_id: Optional[uuid.UUID] = None,
        message_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> list[FetchedUrl]:
        safe_limit = min(max(limit, 1), 100)
        try:
            stmt = (
                select(FetchedUrl)
                .join(Conversation)
                .where(
                    FetchedUrl.conversation_id == conversation_id,
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    ),
                )
                .order_by(FetchedUrl.created_at.asc())
                .limit(safe_limit)
            )
            if research_plan_id is not None:
                stmt = stmt.where(FetchedUrl.research_plan_id == research_plan_id)
            if message_id is not None:
                stmt = stmt.where(FetchedUrl.message_id == message_id)

            result = await self._s.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError:
            logger.exception(
                "ResearchTraceRepository | list_fetched_urls failed | "
                "conversation_id=%s",
                conversation_id,
            )
            raise
