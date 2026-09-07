from fastapi import APIRouter

from app.domain.schemas.requests_schemas.auth_request import (
    AuthResponse,
    SigninRequest,
    SignupRequest,
)
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(request: SignupRequest) -> AuthResponse:
    service = AuthService()
    return await service.signup(
        username=request.username,
        email=str(request.email),
        password=request.password,
    )


@router.post("/signin", response_model=AuthResponse)
async def signin(request: SigninRequest) -> AuthResponse:
    service = AuthService()
    return await service.signin(
        email=str(request.email),
        password=request.password,
    )