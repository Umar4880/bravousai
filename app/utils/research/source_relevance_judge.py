from typing import Literal, Optional
from pydantic import BaseModel, Field
import logging
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from app.core.prompt_loader import PromptManager
from app.domain.schemas.agents_schemas.research_plan_schema import ResearchPlan

logger = logging.getLogger(__name__)

class SourceRelevanceVerdict(BaseModel):
    result_id: str
    relevance_score: float = Field(description="0.0 - 1.0, how relevant to the research plan")
    content_usefulness: float = Field(description="0.0 - 1.0, how much usable information")
    verdict: Literal["keep", "discard", "needs_extraction"] = Field(
        description="keep if useful, discard if irrelevant/garbage, needs_extraction if domain authoritative but content thin"
    )
    reason: str = Field(description="one-line explanation")

class RelevanceJudgeBatch(BaseModel):
    verdicts: list[SourceRelevanceVerdict]

async def judge_source_relevance(
    llm: BaseChatModel,
    sources: list[dict],
    research_plan: ResearchPlan,
    user_query: str,
    user_instructions: str = "None",
    uploaded_files: str = "None",
    prompt_manager: Optional[PromptManager] = None,
) -> list[SourceRelevanceVerdict]:
    """
    ONE batched LLM call that reviews ALL sources together.
    Returns per-source relevance verdicts.
    """
    if not sources:
        return []

    # Prepare summary of sources to fit in context window
    sources_summary_parts = []
    for s in sources:
        text = s.get("extracted_text") or s.get("snippet") or ""
        text = text.replace("\n", " ")[:300] + ("..." if len(text) > 300 else "")
        sources_summary_parts.append(
            f"- ID: {s.get('result_id')}\n"
            f"  Domain: {s.get('domain')}\n"
            f"  Title: {s.get('title')}\n"
            f"  Content Depth: {s.get('content_depth', 'unknown')}\n"
            f"  Content Source: {s.get('content_source', 'unknown')}\n"
            f"  Preview: {text}\n"
        )
    
    sources_summary = "\n".join(sources_summary_parts)
    must_find_str = "\n".join(f"- {m}" for m in research_plan.must_find) if research_plan.must_find else "None specified"
    
    # Reuse the caller's PromptManager instead of creating a new one each call
    prompt_mng = prompt_manager or PromptManager()
    prompt = prompt_mng.load_agent_system_prompt("source_relevance_judge", include_history=False)
    
    chain = prompt | llm.with_structured_output(RelevanceJudgeBatch)
    
    try:
        result = await chain.ainvoke({
            "research_plan": research_plan.model_dump_json(exclude={"primary_queries", "followup_queries"}),
            "user_query": user_query,
            "user_input": user_query,
            "must_find": must_find_str,
            "sources_summary": sources_summary,
            "user_instructions": user_instructions,
            "uploaded_files": uploaded_files
        })
        
        # Ensure we don't crash if LLM returns weird output
        if not isinstance(result, RelevanceJudgeBatch):
            logger.error("LLM relevance judge returned invalid format.")
            return []
            
        # Filter to make sure it only returns verdicts for IDs we gave it
        valid_ids = {s.get('result_id') for s in sources}
        verdicts = [v for v in result.verdicts if v.result_id in valid_ids]
        
        logger.info(f"Judged {len(verdicts)} sources.")
        return verdicts
    except Exception as e:
        logger.exception("Failed to judge source relevance.")
        # Fail open: if LLM fails, we just don't discard anything
        return []


