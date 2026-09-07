from typing import Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class MainAgentState(BaseModel):
    """The conversational state for the user-facing Main Agent."""
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
