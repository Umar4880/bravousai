from collections.abc import AsyncIterator
import logging
from pathlib import Path
from typing import Any, Optional, Sequence, Union
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.core.llm_provider import LLMFactory
from app.ai.agents.main_agent.state import MainAgentState
from app.ai.tools.deep_research_tool import deep_research_tool

logger = logging.getLogger(__name__)


def load_main_agent_prompt() -> str:
    """Load the system prompt governing user interactions and agent delegation."""
    path = Path(__file__).parent / "prompt.md"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class MainAgent:
    """Primary user-facing conversational orchestrator.
    
    Interacts directly with the user and autonomously invokes specialized tools
    (e.g. Deep Research) based on user intent, explicit requests, or query complexity.
    """

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        tools: Optional[Sequence[BaseTool]] = None,
        checkpointer: Optional[Any] = None,
    ):
        self.llm = llm or LLMFactory.get_llm(agent_name="main_agent")
        self.tools = list(tools) if tools is not None else [deep_research_tool]
        self.system_prompt = load_main_agent_prompt()
        self.checkpointer = checkpointer

        # Bind tools to the model
        self.bound_llm = self.llm.bind_tools(self.tools)
        self.graph: CompiledStateGraph = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph:
        """Construct the LangGraph ReAct execution graph."""
        workflow = StateGraph(MainAgentState)

        # Agent decision node
        async def agent_node(state: MainAgentState, config: RunnableConfig) -> dict[str, Any]:
            messages = list(state.messages)
            
            # Ensure the system prompt is prepended if not already there
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=self.system_prompt)] + messages

            response = await self.bound_llm.ainvoke(messages, config=config)
            return {"messages": [response]}

        # Tool execution node
        tool_node = ToolNode(self.tools)

        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)

        workflow.set_entry_point("agent")

        # Route to tools if tool_calls are present, otherwise finish
        workflow.add_conditional_edges("agent", tools_condition)
        workflow.add_edge("tools", "agent")

        return workflow.compile(checkpointer=self.checkpointer)

    async def ainvoke(
        self,
        input_data: Union[dict[str, Any], MainAgentState, str],
        config: Optional[RunnableConfig] = None,
    ) -> MainAgentState:
        """Run the main agent graph to completion."""
        if isinstance(input_data, str):
            payload = {"messages": [HumanMessage(content=input_data)],}
        elif isinstance(input_data, MainAgentState):
            payload = input_data.model_dump()
        else:
            payload = input_data

        result = await self.graph.ainvoke(payload, config=config)
        return MainAgentState(**result)

    async def astream(
        self,
        input_data: Union[dict[str, Any], MainAgentState, str],
        config: Optional[RunnableConfig] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream real-time events, token deltas, and tool telemetry for the frontend SSE stream."""
        if isinstance(input_data, str):
            payload = {
                "messages": [HumanMessage(content=input_data)],
            }
        elif isinstance(input_data, MainAgentState):
            payload = input_data.model_dump()
        else:
            payload = input_data

        # Initial agent acknowledgment
        yield {"type": "node_start", "node": "agent", "message": "Analyzing request..."}

        async for mode, data in self.graph.astream(
            input=payload,
            config=config,
            stream_mode=["custom", "updates", "messages"],
        ):
            # 1. Token-by-token text and reasoning streaming from the LLM
            if mode == "messages":
                message_chunk, _metadata = data
                # Stream reasoning tokens if present
                reasoning_delta = getattr(message_chunk, "additional_kwargs", {}).get("reasoning_content")
                if reasoning_delta:
                    yield {"type": "reasoning_delta", "node": "agent", "content": reasoning_delta}

                if hasattr(message_chunk, "content") and message_chunk.content:
                    # Ignore tool call argument chunks — only stream human-facing text
                    if not getattr(message_chunk, "tool_call_chunks", None):
                        text_delta = (
                            message_chunk.content
                            if isinstance(message_chunk.content, str)
                            else "".join(c.get("text", "") for c in message_chunk.content if isinstance(c, dict))
                        )
                        if text_delta:
                            yield {"type": "node_delta", "node": "agent", "content": text_delta}

            # 2. Node lifecycle & tool dispatch detection
            elif mode == "updates":
                if isinstance(data, dict):
                    # Check if the agent decided to invoke any tool (e.g. deep_research)
                    if "agent" in data:
                        for msg in data["agent"].get("messages", []):
                            tool_calls = getattr(msg, "tool_calls", None)
                            if tool_calls:
                                for tc in tool_calls:
                                    t_name = tc.get("name", "tool") if isinstance(tc, dict) else getattr(tc, "name", "tool")
                                    if t_name == "deep_research":
                                        yield {
                                            "type": "node_start",
                                            "node": "deep_research",
                                            "message": "Initiating deep research investigation...",
                                        }
                                        yield {
                                            "type": "research_phase",
                                            "node": "deep_research",
                                            "phase": "plan",
                                            "message": "Scoping research plan...",
                                            "status": "active",
                                        }
                                    else:
                                        yield {
                                            "type": "node_start",
                                            "node": t_name,
                                            "message": f"Calling tool {t_name}...",
                                        }

                    # Tool finished executing
                    if "tools" in data:
                        yield {
                            "type": "node_end",
                            "node": "deep_research",
                            "message": "Deep research complete.",
                        }

            # 3. Custom telemetry events from Deep Research sub-engines
            elif mode == "custom":
                if isinstance(data, dict):
                    evt_type = data.get("type")
                    msg = data.get("message", "")
                    d = data.get("data", {})

                    if evt_type == "research_scoped":
                        yield {"type": "research_phase", "node": "deep_research", "phase": "plan", "message": msg, "status": "done"}
                        yield {"type": "research_phase", "node": "deep_research", "phase": "search", "message": "Searching web for evidence...", "status": "active"}
                    elif evt_type == "search_dispatched":
                        yield {"type": "search_query_started", "node": "deep_research", "query": d.get("query", "")}
                    elif evt_type == "search_completed":
                        yield {"type": "search_query_completed", "node": "deep_research", "query": d.get("query", ""), "result_count": d.get("result_count", 0)}
                        for u in d.get("urls", []):
                            yield {"type": "search_result_found", "node": "deep_research", "result_id": u, "url": u}
                    elif evt_type == "evidence_added":
                        yield {
                            "type": "source_extraction_completed",
                            "node": "deep_research",
                            "message": msg,
                            "successfully_extracted": d.get("evidence_count", 0),
                            "selected_sources": d.get("sources_analyzed", 0),
                            "partial": 0, "failed": 0, "skipped": 0, "snippet_fallbacks": 0, "total_cleaned_chars": 0,
                        }
                    elif evt_type == "gap_analysis_completed":
                        if not d.get("is_sufficient"):
                            yield {
                                "type": "follow_up_research_started",
                                "node": "deep_research",
                                "iteration": 1,
                                "approved_query_count": len(d.get("follow_up_queries", [])),
                                "rejected_query_count": 0,
                                "message": msg,
                            }
                        else:
                            yield {"type": "research_phase", "node": "deep_research", "phase": "synthesize", "message": "Synthesizing final report...", "status": "active"}
                    elif evt_type in ("section_drafting_started", "section_drafted"):
                        yield {"type": "research_phase", "node": "deep_research", "phase": "synthesize", "message": msg, "status": "active"}
                    elif evt_type == "research_completed":
                        yield {"type": "research_phase", "node": "deep_research", "phase": "synthesize", "message": "Deep research complete.", "status": "done"}

        yield {"type": "node_end", "node": "agent", "message": "Response complete."}


def create_main_agent(
    llm: Optional[BaseChatModel] = None,
    tools: Optional[Sequence[BaseTool]] = None,
    checkpointer: Optional[Any] = None,
) -> MainAgent:
    """Factory helper to instantiate a configured MainAgent."""
    return MainAgent(
        llm=llm,
        tools=tools,
        checkpointer=checkpointer,
    )
