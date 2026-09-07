import logging
import uuid
from typing import Optional

from app.domain.repositories.base import BaseRepository
from app.domain.entities import Conversation, Project

from sqlalchemy import select, update, delete
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class ConversationRepository(BaseRepository):
    """
    Repository for Conversation model operations.
    
    Note: This repository does NOT commit transactions.
    The caller (service layer) is responsible for commit/rollback.
    """

    async def create(self, project_id: uuid.UUID, title: str) -> Conversation:
        """
        Create a new conversation.
        
        Returns:
            The created Conversation object with its generated ID.
        """
        try:
            conversation = Conversation(project_id=project_id, title=title)
            self._s.add(conversation)
            await self._s.flush()  
            
            logger.debug(
                "ConversationRepository | created | project_id=%s | conversation_id=%s",
                project_id,
                conversation.id
            )
            return conversation
            
        except SQLAlchemyError:
            logger.exception(
                "ConversationRepository | create failed | project_id=%s",
                project_id
            )
            raise

    async def get_by_id(
        self, 
        conversation_id: uuid.UUID, 
        user_id: str
    ) -> Optional[Conversation]:
        """
        Fetch a conversation by ID, ensuring it belongs to the user.
        
        Returns:
            Conversation object if found, else None.
        """
        try:
            stmt = select(Conversation).where(
                Conversation.id == conversation_id,  
                Conversation.project_id.in_(
                    select(Project.id).where(Project.user_id == user_id)
                )
            )
            result = await self._s.execute(stmt)
            conversation = result.scalar_one_or_none()  
            
            logger.debug(
                "ConversationRepository | get_by_id | user_id=%s | conversation_id=%s | found=%s",
                user_id,
                conversation_id,
                conversation is not None
            )
            return conversation
            
        except SQLAlchemyError:
            logger.exception(
                "ConversationRepository | get_by_id failed | user_id=%s | conversation_id=%s",
                user_id,
                conversation_id
            )
            raise

    async def update_title(
        self, 
        conversation_id: uuid.UUID, 
        user_id: str, 
        title: str
    ) -> bool:
        """
        Update conversation title.
        
        Returns:
            True if at least one row was updated, False otherwise.
        """
        try:
            stmt = (
                update(Conversation)
                .where(
                    Conversation.id == conversation_id,
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    )
                )
                .values(title=title)
            )
            result = await self._s.execute(stmt)
            await self._s.flush()  # Persist without committing
            
            updated = result.rowcount > 0
            
            logger.debug(
                "ConversationRepository | update_title | user_id=%s | conversation_id=%s | updated=%s",
                user_id,
                conversation_id,
                updated
            )
            return updated
            
        except SQLAlchemyError:
            logger.exception(
                "ConversationRepository | update_title failed | user_id=%s | conversation_id=%s",
                user_id,
                conversation_id
            )
            raise

    async def delete(self, conversation_id: uuid.UUID, user_id: str) -> bool:
        """
        Delete a conversation, ensuring it belongs to the user.
        
        Returns:
            True if deleted, False if not found.
        """
        try:
            stmt = (
                delete(Conversation)
                .where(
                    Conversation.id == conversation_id,
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    )
                )
            )
            result = await self._s.execute(stmt)
            await self._s.flush()
            
            deleted = result.rowcount > 0
            
            logger.debug(
                "ConversationRepository | delete | user_id=%s | conversation_id=%s | deleted=%s",
                user_id,
                conversation_id,
                deleted
            )
            return deleted
            
        except SQLAlchemyError:
            logger.exception(
                "ConversationRepository | delete failed | user_id=%s | conversation_id=%s",
                user_id,
                conversation_id
            )
            raise

    async def list_by_user(
        self, 
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> list[Conversation]:
        """
        List conversations for a user, ordered by most recent first.
        """
        try:
            stmt = (
                select(Conversation)
                .where(
                    Conversation.project_id.in_(
                        select(Project.id).where(Project.user_id == user_id)
                    )
                )
                .order_by(Conversation.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self._s.execute(stmt)
            conversations = result.scalars().all()
            
            logger.debug(
                "ConversationRepository | list_by_user | user_id=%s | count=%s",
                user_id,
                len(conversations)
            )
            return list(conversations)
            
        except SQLAlchemyError:
            logger.exception(
                "ConversationRepository | list_by_user failed | user_id=%s",
                user_id
            )
            raise

    async def list_by_project(
        self,
        *,
        project_id: uuid.UUID,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversation]:
        try:
            stmt = (
                select(Conversation)
                .join(Project)
                .where(
                    Conversation.project_id == project_id,
                    Project.user_id == user_id,
                )
                .order_by(Conversation.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self._s.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError:
            logger.exception(
                "ConversationRepository | list_by_project failed | user_id=%s | project_id=%s",
                user_id,
                project_id,
            )
            raise
