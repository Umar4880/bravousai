import uuid

from fastapi import APIRouter, HTTPException, Query

from app.db.unit_of_work import UnitOfWork
from app.domain.schemas.requests_schemas.project_request import (
    ProjectCreateRequest,
    ProjectInstructionsRequest,
    ProjectUpdateRequest,
)


router = APIRouter(prefix="/projects", tags=["projects"])


def _project_payload(project, files=None) -> dict:
    project_files = files if files is not None else []
    return {
        "id": str(project.id),
        "user_id": str(project.user_id),
        "title": project.title,
        "description": project.description,
        "instructions": project.instructions,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "files": [_file_payload(file) for file in project_files],
    }


def _file_payload(file) -> dict:
    return {
        "id": str(file.id),
        "user_id": str(file.user_id),
        "project_id": str(file.project_id) if file.project_id else None,
        "conversation_id": str(file.conversation_id) if file.conversation_id else None,
        "original_filename": file.original_filename,
        "safe_filename": file.safe_filename,
        "content_type": file.content_type,
        "size_bytes": file.size_bytes,
        "sha256": file.sha256,
        "storage_bucket": file.storage_bucket,
        "storage_key": file.storage_key,
        "status": file.status,
        "created_at": file.created_at.isoformat(),
        "deleted_at": file.deleted_at.isoformat() if file.deleted_at else None,
    }


@router.get("")
async def list_projects(user_id: uuid.UUID = Query(...)) -> dict:
    async with UnitOfWork() as uow:
        projects = await uow.projects.list_by_user(user_id=user_id)
        files_by_project = {
            project.id: await uow.projects.list_files(project_id=project.id, user_id=user_id)
            for project in projects
        }

    return {
        "projects": [
            _project_payload(project, files_by_project.get(project.id, []))
            for project in projects
        ]
    }


@router.post("", status_code=201)
async def create_project(payload: ProjectCreateRequest) -> dict:
    title = " ".join(payload.title.split())[:160]
    if not title:
        raise HTTPException(status_code=422, detail="Project title is required.")

    async with UnitOfWork() as uow:
        project = await uow.projects.create(
            user_id=payload.user_id,
            title=title,
            description=payload.description.strip(),
            instructions=payload.instructions.strip(),
        )
        await uow.commit()
        files = await uow.projects.list_files(project_id=project.id, user_id=payload.user_id)

    return _project_payload(project, files)


@router.get("/{project_id}")
async def get_project(project_id: uuid.UUID, user_id: uuid.UUID = Query(...)) -> dict:
    async with UnitOfWork() as uow:
        project = await uow.projects.get_owned(project_id=project_id, user_id=user_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        files = await uow.projects.list_files(project_id=project_id, user_id=user_id)

    return _project_payload(project, files)


@router.patch("/{project_id}")
async def update_project(project_id: uuid.UUID, payload: ProjectUpdateRequest) -> dict:
    title = None if payload.title is None else " ".join(payload.title.split())[:160]
    if payload.title is not None and not title:
        raise HTTPException(status_code=422, detail="Project title is required.")

    async with UnitOfWork() as uow:
        project = await uow.projects.update(
            project_id=project_id,
            user_id=payload.user_id,
            title=title,
            description=payload.description.strip() if payload.description is not None else None,
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        await uow.commit()
        files = await uow.projects.list_files(project_id=project_id, user_id=payload.user_id)

    return _project_payload(project, files)


@router.patch("/{project_id}/instructions")
async def update_project_instructions(project_id: uuid.UUID, payload: ProjectInstructionsRequest) -> dict:
    async with UnitOfWork() as uow:
        project = await uow.projects.update_instructions(
            project_id=project_id,
            user_id=payload.user_id,
            instructions=payload.instructions,
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        await uow.commit()
        files = await uow.projects.list_files(project_id=project_id, user_id=payload.user_id)

    return _project_payload(project, files)


@router.delete("/{project_id}")
async def delete_project(project_id: uuid.UUID, user_id: uuid.UUID = Query(...)) -> dict:
    async with UnitOfWork() as uow:
        deleted = await uow.projects.delete(project_id=project_id, user_id=user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found.")
        await uow.commit()

    return {"deleted": True, "id": str(project_id)}

