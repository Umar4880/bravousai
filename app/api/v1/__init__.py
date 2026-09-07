from fastapi import APIRouter

from app.api.v1.artifact_routes import router as artifact_router
from app.api.v1.file_routes import router as file_router
from app.api.v1.project_routes import router as project_router

router = APIRouter()
router.include_router(artifact_router)
router.include_router(file_router)
router.include_router(project_router)

try:
    from app.api.v1.routes import router as chat_router
    from app.api.v1.auth_routes import router as auth_router
except ModuleNotFoundError:
    chat_router = None
    auth_router = None

if chat_router is not None:
    router.include_router(chat_router)
if auth_router is not None:
    router.include_router(auth_router)

__all__ = ["router"]
