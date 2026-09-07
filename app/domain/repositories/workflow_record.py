import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.domain.entities import Artifact, Conversation, Project, WorkflowRecord
from app.domain.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class WorkflowRecordRepository(BaseRepository):
    """
    Persists supervisor plans and execution progress.

    This repository never commits transactions.
    UnitOfWork owns commit and rollback.
    """

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

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        user_query: str,
        plan_json: dict[str, Any],
        message_id: Optional[uuid.UUID] = None,
        intent: Optional[str] = None,
        mode: Optional[str] = None,
        execution_path: Optional[list[str]] = None,
        current_step_index: int = 0,
        status: str = "completed",
        route_reason: str = "",
        confidence: float = 0.0,
    ) -> WorkflowRecord:
        try:
            await self._ensure_owned_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
            )

            record = WorkflowRecord(
                conversation_id=conversation_id,
                user_query=user_query,
                message_id=message_id,
                plan_json=plan_json,
                intent=intent or plan_json.get("intent"),
                mode=mode or plan_json.get("mode", "instant"),
                execution_path=execution_path or plan_json.get("execution_path", []),
                current_step_index=current_step_index or plan_json.get("current_step_index", 0),
                status=status or plan_json.get("status", "completed") or "completed",
                route_reason=route_reason or plan_json.get("route_reason", ""),
                confidence=confidence or plan_json.get("confidence", 0.0) or 0.0,
            )

            self._s.add(record)
            await self._s.flush()

            logger.debug(
                "WorkflowRecordRepository | created | user_id=%s | "
                "conversation_id=%s | workflow_record_id=%s",
                user_id,
                conversation_id,
                record.id,
            )

            return record

        except SQLAlchemyError:
            logger.exception(
                "WorkflowRecordRepository | create failed | "
                "user_id=%s | conversation_id=%s",
                user_id,
                conversation_id,
            )
            raise

    async def get_owned_by_id(
        self,
        *,
        workflow_record_id: uuid.UUID,
        user_id: str,
        conversation_id: uuid.UUID,
    ) -> Optional[WorkflowRecord]:
        try:
            stmt = (
                select(WorkflowRecord)
                .join(Conversation)
                .where(
                    WorkflowRecord.id == workflow_record_id,
                    WorkflowRecord.conversation_id == conversation_id,
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    ),
                )
            )

            result = await self._s.execute(stmt)
            return result.scalar_one_or_none()

        except SQLAlchemyError:
            logger.exception(
                "WorkflowRecordRepository | get_owned_by_id failed | "
                "workflow_record_id=%s | user_id=%s",
                workflow_record_id,
                user_id,
            )
            raise

    async def get_latest(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
    ) -> Optional[WorkflowRecord]:
        try:
            stmt = (
                select(WorkflowRecord)
                .join(Conversation)
                .where(
                    WorkflowRecord.conversation_id == conversation_id,
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    ),
                )
                .order_by(WorkflowRecord.created_at.desc())
                .limit(1)
            )

            result = await self._s.execute(stmt)
            return result.scalar_one_or_none()

        except SQLAlchemyError:
            logger.exception(
                "WorkflowRecordRepository | get_latest failed | "
                "user_id=%s | conversation_id=%s",
                user_id,
                conversation_id,
            )
            raise

    async def list_recent(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        limit: int = 3,
    ) -> list[WorkflowRecord]:
        safe_limit = min(max(limit, 1), 10)

        try:
            stmt = (
                select(WorkflowRecord)
                .join(Conversation)
                .where(
                    WorkflowRecord.conversation_id == conversation_id,
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    ),
                )
                .order_by(WorkflowRecord.created_at.desc())
                .limit(safe_limit)
            )

            result = await self._s.execute(stmt)
            return list(result.scalars().all())

        except SQLAlchemyError:
            logger.exception(
                "WorkflowRecordRepository | list_recent failed | "
                "user_id=%s | conversation_id=%s",
                user_id,
                conversation_id,
            )
            raise

    async def update_progress(
        self,
        *,
        workflow_record_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_id: str,
        current_step_index: int,
        status: str,
    ) -> bool:
        try:
            stmt = (
                update(WorkflowRecord)
                .where(
                    WorkflowRecord.id == workflow_record_id,
                    WorkflowRecord.conversation_id == conversation_id,
                    WorkflowRecord.conversation_id.in_(
                        select(Conversation.id).where(
                            Conversation.project_id.in_(
                                select(Project.id).where(Project.user_id == user_id)
                            )
                        )
                    ),
                )
                .values(
                    current_step_index=current_step_index,
                    status=status,
                )
            )

            result = await self._s.execute(stmt)
            await self._s.flush()

            return result.rowcount > 0

        except SQLAlchemyError:
            logger.exception(
                "WorkflowRecordRepository | update_progress failed | "
                "workflow_record_id=%s | user_id=%s",
                workflow_record_id,
                user_id,
            )
            raise

    async def attach_artifact(
        self,
        *,
        workflow_record_id: uuid.UUID,
        artifact_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_id: str,
    ) -> bool:
        """
        Attach generated artifact after verifying artifact ownership.
        """
        try:
            artifact_stmt = select(Artifact.id).where(
                Artifact.id == artifact_id,
                Artifact.conversation_id == conversation_id,
                Artifact.conversation_id.in_(
                    select(Conversation.id).where(
                        Conversation.project_id.in_(
                            select(Project.id).where(Project.user_id == user_id)
                        )
                    )
                ),
            )

            artifact_result = await self._s.execute(artifact_stmt)

            if artifact_result.scalar_one_or_none() is None:
                raise PermissionError(
                    "Artifact not found or does not belong to authenticated user."
                )

            stmt = (
                update(WorkflowRecord)
                .where(
                    WorkflowRecord.id == workflow_record_id,
                    WorkflowRecord.conversation_id == conversation_id,
                    WorkflowRecord.conversation_id.in_(
                        select(Conversation.id).where(
                            Conversation.project_id.in_(
                                select(Project.id).where(Project.user_id == user_id)
                            )
                        )
                    ),
                )
                .values(artifact_id=artifact_id)
            )

            result = await self._s.execute(stmt)
            await self._s.flush()

            return result.rowcount > 0

        except SQLAlchemyError:
            logger.exception(
                "WorkflowRecordRepository | attach_artifact failed | "
                "workflow_record_id=%s | artifact_id=%s | user_id=%s",
                workflow_record_id,
                artifact_id,
                user_id,
            )
            raise

    async def get_for_message(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        message_id: uuid.UUID,
    ) -> Optional[WorkflowRecord]:
        try:
            stmt = (
                select(WorkflowRecord)
                .join(Conversation)
                .where(
                    WorkflowRecord.conversation_id == conversation_id,
                    WorkflowRecord.message_id == message_id,
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    ),
                )
                .order_by(WorkflowRecord.created_at.desc())
                .limit(1)
            )

            result = await self._s.execute(stmt)
            return result.scalar_one_or_none()

        except SQLAlchemyError:
            logger.exception(
                "WorkflowRecordRepository | get_for_message failed | "
                "message_id=%s | user_id=%s",
                message_id,
                user_id,
            )
            raise
