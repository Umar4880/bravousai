import uuid

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile



router = APIRouter(tags=["files"])


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




# @router.post("/files/upload", status_code=201)
# async def upload_file(
#     user_id: uuid.UUID = Form(...),
#     project_id: uuid.UUID | None = Form(None),
#     conversation_id: uuid.UUID | None = Form(None),
#     file: UploadFile = File(...),
# ) -> dict:
#     try:
#         metadata = await _file_service().upload_project_file(
#             user_id=user_id,
#             project_id=project_id,
#             conversation_id=conversation_id,
#             upload_file=file,
#         )
#     except ValueError as exc:
#         detail = str(exc)
#         status_code = 413 if "maximum size" in detail else 415
#         raise HTTPException(status_code=status_code, detail=detail) from exc
#     except PermissionError as exc:
#         raise HTTPException(status_code=404, detail=str(exc)) from exc

#     return _file_payload(metadata)


# @router.get("/files/{file_id}")
# async def get_file_metadata(file_id: uuid.UUID, user_id: uuid.UUID = Query(...)) -> dict:
#     try:
#         metadata = await _file_service().get_file_metadata(file_id=file_id, user_id=user_id)
#     except PermissionError as exc:
#         raise HTTPException(status_code=404, detail=str(exc)) from exc

#     return _file_payload(metadata)


# @router.get("/files/{file_id}/download")
# async def download_file(file_id: uuid.UUID, user_id: uuid.UUID = Query(...)) -> Response:
#     try:
#         downloaded = await _file_service().download_project_file(file_id=file_id, user_id=user_id)
#     except PermissionError as exc:
#         raise HTTPException(status_code=404, detail=str(exc)) from exc

#     filename = downloaded.metadata.safe_filename.replace('"', "")
#     return Response(
#         content=downloaded.content,
#         media_type=downloaded.metadata.content_type,
#         headers={"Content-Disposition": f'attachment; filename="{filename}"'},
#     )


# @router.get("/projects/{project_id}/files")
# async def list_project_files(project_id: uuid.UUID, user_id: uuid.UUID = Query(...)) -> dict:
#     files = await _file_service().list_project_files(user_id=user_id, project_id=project_id)
#     return {"files": [_file_payload(file) for file in files]}


# @router.delete("/files/{file_id}")
# async def delete_file(file_id: uuid.UUID, user_id: uuid.UUID = Query(...)) -> dict:
#     try:
#         deleted = await _file_service().delete_project_file(file_id=file_id, user_id=user_id)
#     except PermissionError as exc:
#         raise HTTPException(status_code=404, detail=str(exc)) from exc

#     return {"deleted": True, "id": str(deleted.id)}
