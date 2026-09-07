import logging
import uuid
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from app.domain.entities import Artifact, ArtifactVersion, Conversation, Project
from app.domain.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ArtifactRepository(BaseRepository):
    """
    Artifact repository.

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
        artifact_type: str,
        title: str,
        content: str,
        short_summary: Optional[str] = None,
        original_user_query: Optional[str] = None,
        message_id: Optional[uuid.UUID] = None,
        parent_artifact_id: Optional[uuid.UUID] = None,
        version: int = 1,
    ) -> Artifact:
        try:
            await self._ensure_owned_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
            )

            artifact = Artifact(
                conversation_id=conversation_id,
                artifact_type=artifact_type,
                title=title,
                short_summary=short_summary,
                content=content,
                original_user_query=original_user_query,
                message_id=message_id,
                parent_artifact_id=parent_artifact_id,
                version=version,
            )

            self._s.add(artifact)
            await self._s.flush()

            logger.debug(
                "ArtifactRepository | created | user_id=%s | "
                "conversation_id=%s | artifact_id=%s | artifact_type=%s",
                user_id,
                conversation_id,
                artifact.id,
                artifact_type,
            )

            return artifact

        except SQLAlchemyError:
            logger.exception(
                "ArtifactRepository | create failed | user_id=%s | conversation_id=%s",
                user_id,
                conversation_id,
            )
            raise

    async def get_owned_by_id(
        self,
        *,
        artifact_id: uuid.UUID,
        user_id: str,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> Optional[Artifact]:
        try:
            stmt = (
                select(Artifact)
                .join(Conversation)
                .where(
                    Artifact.id == artifact_id,
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    ),
                )
            )

            if conversation_id is not None:
                stmt = stmt.where(
                    Artifact.conversation_id == conversation_id,
                )

            result = await self._s.execute(stmt)
            return result.scalar_one_or_none()

        except SQLAlchemyError:
            logger.exception(
                "ArtifactRepository | get_owned_by_id failed | "
                "user_id=%s | artifact_id=%s",
                user_id,
                artifact_id,
            )
            raise

    async def list_recent_cards(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        limit: int = 5,
    ) -> list[Artifact]:
        safe_limit = min(max(limit, 1), 10)

        try:
            stmt = (
                select(Artifact)
                .where(
                    Artifact.conversation_id == conversation_id,
                    Artifact.conversation_id.in_(
                        select(Conversation.id).where(
                            Conversation.project_id.in_(
                                select(Project.id).where(Project.user_id == user_id)
                            )
                        )
                    ),
                )
                .order_by(Artifact.updated_at.desc())
                .limit(safe_limit)
            )

            result = await self._s.execute(stmt)
            return list(result.scalars().all())

        except SQLAlchemyError:
            logger.exception(
                "ArtifactRepository | list_recent_cards failed | "
                "user_id=%s | conversation_id=%s",
                user_id,
                conversation_id,
            )
            raise

    async def search_cards(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        query: str,
        limit: int = 3,
    ) -> list[Artifact]:
        """
        Search compact artifact metadata.

        Do not return full content to supervisor.
        Service layer converts rows into ArtifactCard schemas.
        """
        safe_query = query.strip()[:300]
        safe_limit = min(max(limit, 1), 5)

        if not safe_query:
            return []

        try:
            stmt = (
                select(Artifact)
                .where(
                    Artifact.conversation_id == conversation_id,
                    Artifact.conversation_id.in_(
                        select(Conversation.id).where(
                            Conversation.project_id.in_(
                                select(Project.id).where(Project.user_id == user_id)
                            )
                        )
                    ),
                    or_(
                        Artifact.title.icontains(
                            safe_query,
                            autoescape=True,
                        ),
                        Artifact.short_summary.icontains(
                            safe_query,
                            autoescape=True,
                        ),
                        Artifact.original_user_query.icontains(
                            safe_query,
                            autoescape=True,
                        ),
                    ),
                )
                .order_by(Artifact.updated_at.desc())
                .limit(safe_limit)
            )

            result = await self._s.execute(stmt)

            artifacts = list(result.scalars().all())

            logger.debug(
                "ArtifactRepository | search_cards | user_id=%s | "
                "conversation_id=%s | matches=%s",
                user_id,
                conversation_id,
                len(artifacts),
            )

            return artifacts

        except SQLAlchemyError:
            logger.exception(
                "ArtifactRepository | search_cards failed | "
                "user_id=%s | conversation_id=%s",
                user_id,
                conversation_id,
            )
            raise

    async def list_for_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        limit: int = 100,
    ) -> list[Artifact]:
        try:
            stmt = (
                select(Artifact)
                .where(
                    Artifact.conversation_id == conversation_id,
                    Artifact.conversation_id.in_(
                        select(Conversation.id).where(
                            Conversation.project_id.in_(
                                select(Project.id).where(Project.user_id == user_id)
                            )
                        )
                    )
                )
                .order_by(Artifact.created_at.asc())
                .limit(limit)
            )

            result = await self._s.execute(stmt)
            return list(result.scalars().all())

        except SQLAlchemyError:
            logger.exception(
                "ArtifactRepository | list_for_conversation failed | user_id=%s | conversation_id=%s",
                user_id,
                conversation_id,
            )
            raise

    async def list_for_message(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: str,
        message_id: uuid.UUID,
        limit: int = 5,
    ) -> list[Artifact]:
        safe_limit = min(max(limit, 1), 10)

        try:
            stmt = (
                select(Artifact)
                .where(
                    Artifact.conversation_id == conversation_id,
                    Artifact.message_id == message_id,
                    Artifact.conversation_id.in_(
                        select(Conversation.id).where(
                            Conversation.project_id.in_(
                                select(Project.id).where(Project.user_id == user_id)
                            )
                        )
                    ),
                )
                .options(selectinload(Artifact.versions))
                .order_by(Artifact.updated_at.desc())
                .limit(safe_limit)
            )

            result = await self._s.execute(stmt)
            return list(result.scalars().all())

        except SQLAlchemyError:
            logger.exception(
                "ArtifactRepository | list_for_message failed | "
                "user_id=%s | message_id=%s",
                user_id,
                message_id,
            )
            raise

    async def create_version(
        self,
        *,
        artifact_id: uuid.UUID,
        version: int,
        plan_json: dict,
        spec_json: dict,
        html_body: str,
        css: str,
        javascript: Optional[str],
        validation_report: dict,
    ) -> ArtifactVersion:
        artifact_version = ArtifactVersion(
            artifact_id=artifact_id,
            version=version,
            plan_json=plan_json,
            spec_json=spec_json,
            html_body=html_body,
            css=css,
            javascript=javascript,
            validation_report=validation_report,
        )
        self._s.add(artifact_version)
        await self._s.flush()
        return artifact_version

    async def get_version_by_id(
        self,
        *,
        version_id: uuid.UUID,
    ) -> Optional[ArtifactVersion]:
        result = await self._s.execute(
            select(ArtifactVersion).where(ArtifactVersion.id == version_id)
        )
        return result.scalar_one_or_none()
