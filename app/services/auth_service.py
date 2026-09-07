from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password, verify_password
from app.db.unit_of_work import UnitOfWork
from app.domain.schemas.requests_schemas.auth_request import AuthResponse


class AuthService:
    async def signup(
        self,
        *,
        username: str,
        email: str,
        password: str,
    ) -> AuthResponse:
        async with UnitOfWork() as uow:
            existing_email = await uow.users.get_by_email(email)
            if existing_email is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already exists.",
                )

            existing_username = await uow.users.get_by_username(username)
            if existing_username is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists.",
                )

            try:
                user = await uow.users.create(
                    username=username,
                    email=email,
                    password_hash=hash_password(password),
                )
                await uow.commit()
            except IntegrityError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User already exists.",
                ) from exc

            return AuthResponse(
                user_id=user.id,
                username=user.username,
                email=user.email,
            )

    async def signin(
        self,
        *,
        email: str,
        password: str,
    ) -> AuthResponse:
        async with UnitOfWork() as uow:
            user = await uow.users.get_by_email(email)

            if user is None or not verify_password(password, user.password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password.",
                )

            return AuthResponse(
                user_id=user.id,
                username=user.username,
                email=user.email,
            )