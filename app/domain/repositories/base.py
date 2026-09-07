from sqlalchemy.ext.asyncio import AsyncSession

class BaseRepository:
    def __init__(self, session: AsyncSession):
        self._s = session