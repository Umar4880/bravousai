import secrets
import uuid

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
import io

from app.domain.schemas.agents_schemas.presentation_schema import ArtifactBundle
from app.utils.presentation.artifact_validation import csp_header, render_standalone_html
from app.services.object_storage_service import ObjectStorageService
from app.core.config import setting

try:
    from app.db.unit_of_work import UnitOfWork
except ModuleNotFoundError:
    UnitOfWork = None


router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{version_id}/render")
async def render_artifact(version_id: uuid.UUID) -> Response:
    try:
        if UnitOfWork is None:
            raise RuntimeError("Database driver is unavailable.")
        async with UnitOfWork() as uow:
            version = await uow.artifacts.get_version_by_id(version_id=version_id)
            if version is None:
                raise HTTPException(status_code=404, detail="Artifact version not found.")
            bundle = ArtifactBundle(
                html_body=version.html_body,
                css=version.css,
                javascript=version.javascript,
            )
            title = ""
            if isinstance(version.spec_json, dict):
                title = str(version.spec_json.get("title") or "")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    nonce = secrets.token_urlsafe(18)
    html = render_standalone_html(
        bundle=bundle,
        title=title or "Research artifact",
        nonce=nonce,
    )
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Security-Policy": csp_header(nonce),
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        },
    )

@router.get("/{version_id}/download")
async def download_artifact(version_id: uuid.UUID, inline: bool = False):
    try:
        if UnitOfWork is None:
            raise RuntimeError("Database driver is unavailable.")
        async with UnitOfWork() as uow:
            version = await uow.artifacts.get_version_by_id(version_id=version_id)
            if version is None:
                raise HTTPException(status_code=404, detail="Artifact version not found.")
            
            # Check if this artifact is stored in MinIO
            spec = version.spec_json if isinstance(version.spec_json, dict) else {}
            minio_key = spec.get("minio_object_key")
            title = str(spec.get("title") or f"artifact_{version_id}")
            
            if minio_key:
                # Fetch from MinIO
                obj_service = ObjectStorageService()
                try:
                    file_bytes = obj_service.get_object(setting.OBJECT_STORAGE_BUCKET_PROJECT_FILES, minio_key)
                except Exception as e:
                    raise HTTPException(status_code=404, detail=f"File not found in storage: {e}")
                
                # Determine content type and extension
                if minio_key.endswith(".docx"):
                    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    ext = "docx"
                elif minio_key.endswith(".md"):
                    media_type = "text/plain; charset=utf-8"
                    ext = "md"
                else:
                    media_type = "application/octet-stream"
                    ext = minio_key.split(".")[-1] if "." in minio_key else "bin"
                    
                filename = f"{title.replace(' ', '_')}.{ext}"
                
                headers = {}
                if not inline:
                    headers["Content-Disposition"] = f'attachment; filename="{filename}"'
                
                return Response(
                    content=file_bytes,
                    media_type=media_type,
                    headers=headers,
                )
            else:
                # Fallback to HTML stored in DB
                bundle = ArtifactBundle(
                    html_body=version.html_body,
                    css=version.css,
                    javascript=version.javascript,
                )
                nonce = secrets.token_urlsafe(18)
                html = render_standalone_html(
                    bundle=bundle,
                    title=title,
                    nonce=nonce,
                )
                filename = f"{title.replace(' ', '_')}.html"
                return Response(
                    content=html,
                    media_type="text/html; charset=utf-8",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"'
                    }
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
