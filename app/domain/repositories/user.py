import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.domain.entities import User
from app.domain.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    async def create(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> User:
        try:
            kwargs = {
                "username": username,
                "email": email.lower(),
                "password": password_hash,
            }
            if user_id is not None:
                kwargs["id"] = user_id

            user = User(**kwargs)
            self._s.add(user)
            await self._s.flush()
            return user
        except SQLAlchemyError:
            raise

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self._s.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self._s.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self._s.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()