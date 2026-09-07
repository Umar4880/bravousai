import uuid
from typing import Optional

from datetime import datetime, timezone
from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.domain.entities import Project, ProjectFile
from app.domain.repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    async def create(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        description: str = "",
        instructions: str = "",
    ) -> Project:
        project = Project(
            user_id=user_id,
            title=title,
            description=description,
            instructions=instructions,
        )
        self._s.add(project)
        await self._s.flush()
        return project

    async def list_by_user(self, *, user_id: uuid.UUID) -> list[Project]:
        result = await self._s.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.updated_at.desc(), Project.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_owned(self, *, project_id: uuid.UUID, user_id: uuid.UUID | str) -> Optional[Project]:
        result = await self._s.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID | str,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Project]:
        values = {}
        if title is not None:
            values["title"] = title
        if description is not None:
            values["description"] = description
        if not values:
            return await self.get_owned(project_id=project_id, user_id=user_id)

        stmt = (
            update(Project)
            .where(Project.id == project_id, Project.user_id == user_id)
            .values(**values)
            .returning(Project)
        )
        result = await self._s.execute(stmt)
        await self._s.flush()
        return result.scalar_one_or_none()

    async def update_instructions(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID | str,
        instructions: str,
    ) -> Optional[Project]:
        stmt = (
            update(Project)
            .where(Project.id == project_id, Project.user_id == user_id)
            .values(instructions=instructions)
            .returning(Project)
        )
        result = await self._s.execute(stmt)
        await self._s.flush()
        return result.scalar_one_or_none()

    async def delete(self, *, project_id: uuid.UUID, user_id: uuid.UUID | str) -> bool:
        result = await self._s.execute(
            delete(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        await self._s.flush()
        return result.rowcount > 0

    async def create_file_metadata(
        self,
        *,
        user_id: uuid.UUID | str,
        file_id: uuid.UUID,
        project_id: uuid.UUID | None,
        conversation_id: uuid.UUID | None,
        original_filename: str,
        safe_filename: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        storage_bucket: str,
        storage_key: str,
        extracted_text: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> ProjectFile:
        if project_id is not None and await self.get_owned(project_id=project_id, user_id=user_id) is None:
            raise PermissionError("Project not found or does not belong to user.")

        project_file = ProjectFile(
            id=file_id,
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            original_filename=original_filename,
            safe_filename=safe_filename,
            content_type=content_type or "application/octet-stream",
            size_bytes=size_bytes,
            sha256=sha256,
            storage_bucket=storage_bucket,
            storage_key=storage_key,
            status="uploaded",
            extracted_text=extracted_text,
            summary=summary,
        )
        self._s.add(project_file)
        await self._s.flush()
        return project_file

    async def get_file_metadata(
        self,
        *,
        file_id: uuid.UUID,
        user_id: uuid.UUID | str,
        include_deleted: bool = False,
    ) -> Optional[ProjectFile]:
        stmt = select(ProjectFile).where(
            ProjectFile.id == file_id,
            ProjectFile.user_id == user_id,
        )
        if not include_deleted:
            stmt = stmt.where(ProjectFile.status == "uploaded")
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def list_files(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID | str,
    ) -> list[ProjectFile]:
        result = await self._s.execute(
            select(ProjectFile)
            .where(
                ProjectFile.project_id == project_id,
                ProjectFile.user_id == user_id,
                ProjectFile.status == "uploaded",
            )
            .order_by(ProjectFile.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_file_deleted(
        self,
        *,
        file_id: uuid.UUID,
        user_id: uuid.UUID | str,
    ) -> Optional[ProjectFile]:
        stmt = (
            update(ProjectFile)
            .where(
                ProjectFile.id == file_id,
                ProjectFile.user_id == user_id,
                ProjectFile.status == "uploaded",
            )
            .values(status="deleted", deleted_at=datetime.now(timezone.utc))
            .returning(ProjectFile)
        )
        result = await self._s.execute(stmt)
        await self._s.flush()
        return result.scalar_one_or_none()
