from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, AsyncGenerator
from uuid import UUID
import uuid

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool

from app.ai.agents.main_agent import MainAgent
from app.db.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    conversation_id: UUID
    answer: str
    approved: bool = True
    route_reason: str = "completed"
    iteration_count: int = 1
    raw_state: dict[str, Any] = field(default_factory=dict)


class ChatService:
    def __init__(
        self,
        llm: Any | None = None,
        tools: list[BaseTool] | None = None,
        checkpointer: Any | None = None,
    ):
        self.agent = MainAgent(
            llm=llm,
            tools=tools,
            checkpointer=checkpointer,
        )

    async def _resolve_session(
        self,
        uow: UnitOfWork,
        user_id: UUID | str,
        project_id: UUID | str | None,
        conversation_id: UUID | str | None,
        query_preview: str,
    ) -> tuple[UUID, UUID, UUID, bool]:
        """Ensures user, project, and conversation exist in the DB, returning (user_id, project_id, conversation_id, is_new)."""
        uid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))

        # 1. Resolve user
        user = await uow.users.get_by_id(uid)
        if not user:
            user = await uow.users.create(
                user_id=uid,
                username=f"user_{str(uid)[:8]}",
                email=f"{str(uid)[:8]}@bravous.local",
                password_hash="system_managed",
            )

        # 2. Resolve project
        project = None
        if project_id:
            pid = project_id if isinstance(project_id, UUID) else UUID(str(project_id))
            project = await uow.projects.get_owned(project_id=pid, user_id=uid)

        if not project:
            projects = await uow.projects.list_by_user(user_id=uid)
            if projects:
                project = projects[0]
            else:
                project = await uow.projects.create(
                    user_id=uid,
                    title="Default Project",
                )

        # 3. Resolve conversation
        is_new = False
        conv = None
        if conversation_id:
            cid = conversation_id if isinstance(conversation_id, UUID) else UUID(str(conversation_id))
            conv = await uow.conversations.get_by_id(cid, user_id=str(uid))

        if not conv:
            title = query_preview[:60] + ("..." if len(query_preview) > 60 else "")
            conv = await uow.conversations.create(project_id=project.id, title=title)
            is_new = True

        return uid, project.id, conv.id, is_new

    async def stream_message(
        self,
        user_id: UUID,
        user_query: str,
        project_id: UUID | None = None,
        mode: str = "instant",
        conversation_id: UUID | None = None,
        tavily_api_key: str | None = None,
        provider_api_key: str | None = None,
        provider_model: str | None = None,
        wants_artifact: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream conversational events, token deltas, and research telemetry."""
        # 1. Database persistence of initial conversation and user query
        async with UnitOfWork() as uow:
            uid, pid, cid, is_new = await self._resolve_session(
                uow=uow,
                user_id=user_id,
                project_id=project_id,
                conversation_id=conversation_id,
                query_preview=user_query,
            )
            user_msg = await uow.messages.add_message(
                conversation_id=cid,
                user_id=str(uid),
                role="user",
                content=user_query,
            )
            await uow.commit()

        if is_new:
            yield {
                "type": "conversation_created",
                "conversation_id": str(cid),
                "user_message_id": str(user_msg.id) if hasattr(user_msg, "id") else None,
            }

        # 2. Configure agent execution
        now = datetime.now(timezone.utc)
        config: dict[str, Any] = {
            "configurable": {
                "thread_id": str(cid),
            }
        }
        if provider_api_key:
            config["configurable"]["provider_api_key"] = provider_api_key
        if provider_model:
            config["configurable"]["provider_model"] = provider_model

        # 3. Stream agent deltas & telemetry
        accumulated_text: list[str] = []
        accumulated_reasoning: list[str] = []
        async for event in self.agent.astream(
            input_data={
                "messages": [HumanMessage(content=user_query)],
                "user_id": str(uid),
                "conversation_id": str(cid),
            },
            config=config,
        ):
            if event.get("type") == "node_delta":
                accumulated_text.append(event.get("content", ""))
            elif event.get("type") == "reasoning_delta":
                accumulated_reasoning.append(event.get("content", ""))
            yield event

        # 4. Final response persistence and emission
        full_answer = "".join(accumulated_text).strip()
        full_reasoning = "".join(accumulated_reasoning).strip()
        if not full_answer:
            full_answer = "I have completed processing your request."

        try:
            async with UnitOfWork() as uow:
                await uow.messages.add_message(
                    conversation_id=cid,
                    user_id=str(uid),
                    role="assistant",
                    content=full_answer,
                )
                await uow.commit()
        except Exception as exc:
            logger.exception("Failed to persist assistant message | conv_id=%s | err=%s", cid, exc)

        yield {
            "type": "final",
            "conversation_id": str(cid),
            "answer": full_answer,
            "reasoning": full_reasoning or None,
            "approved": True,
            "route_reason": "completed",
            "iteration_count": 1,
            "artifact": None,
        }

    async def handle_message(
        self,
        user_id: UUID,
        project_id: UUID | None,
        user_query: str,
        mode: str = "instant",
        conversation_id: UUID | None = None,
    ) -> ChatResult:
        """Synchronous / batch execution of a message without SSE streaming."""
        async with UnitOfWork() as uow:
            uid, pid, cid, _ = await self._resolve_session(
                uow=uow,
                user_id=user_id,
                project_id=project_id,
                conversation_id=conversation_id,
                query_preview=user_query,
            )
            await uow.messages.add_message(
                conversation_id=cid,
                user_id=str(uid),
                role="user",
                content=user_query,
            )
            await uow.commit()

        config = {"configurable": {"thread_id": str(cid)}}
        state = await self.agent.ainvoke(
            input_data={
                "messages": [HumanMessage(content=user_query)],
                "user_id": str(uid),
                "conversation_id": str(cid),
            },
            config=config,
        )

        answer = ""
        for msg in reversed(state.messages):
            if isinstance(msg, AIMessage) and msg.content:
                if isinstance(msg.content, str):
                    answer = msg.content
                elif isinstance(msg.content, list):
                    answer = "\n".join(
                        c.get("text", "") for c in msg.content if isinstance(c, dict) and "text" in c
                    )
                break

        if not answer:
            answer = "I have completed processing your request."

        try:
            async with UnitOfWork() as uow:
                await uow.messages.add_message(
                    conversation_id=cid,
                    user_id=str(uid),
                    role="assistant",
                    content=answer,
                )
                await uow.commit()
        except Exception as exc:
            logger.exception("Failed to persist assistant message in handle_message | conv_id=%s | err=%s", cid, exc)

        return ChatResult(
            conversation_id=cid,
            answer=answer,
            approved=True,
            route_reason="completed",
            iteration_count=1,
            raw_state=state.model_dump() if hasattr(state, "model_dump") else {},
        )