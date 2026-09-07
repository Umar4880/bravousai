import logging
from typing import Dict
import uuid
import time

from langchain_core.callbacks import AsyncCallbackHandler

logger = logging.getLogger(__name__)

class LoggingCallbackHandler(AsyncCallbackHandler):
    def __init__(self, agent_name: str, user_id: str):
        self._name = agent_name
        self._user_id = user_id
        self._start_time: Dict[uuid.UUID, float] = {}

    async def on_llm_start(
            self, 
            serialized, 
            prompts, 
            *, 
            run_id, 
            parent_run_id = None, 
            tags = None, 
            metadata = None, 
            **kwargs):
        
        self._start_time[run_id] = time.time()

    async def on_chat_model_start(
            self,
            serialized,
            messages,
            *,
            run_id,
            parent_run_id=None,
            tags=None,
            metadata=None,
            **kwargs):

        self._start_time[run_id] = time.time()

    async def on_llm_end(
            self, 
            response, 
            *, 
            run_id, 
            parent_run_id = None, 
            tags = None, 
            **kwargs):
        
        start_time = self._start_time.pop(run_id, time.time())
        duration_ms = (time.time() - start_time) * 1000

        token_usage = {}
        if response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})

        logger.info(
            "LLM call completed",
            extra={
                "event": "llm_call",
                "agent": self._name,
                "user_id": self._user_id,
                "run_id": str(run_id),
                "duration_ms": round(duration_ms, 2),
                "prompt_tokens": token_usage.get("prompt_tokens", 0),
                "completion_tokens": token_usage.get("completion_tokens", 0),
                "total_tokens": token_usage.get("total_tokens", 0),

            }
        )

    async def on_llm_error(
            self, 
            error, 
            *, 
            run_id, 
            parent_run_id = None, 
            tags = None, 
            **kwargs):
        
        start_time = self._start_time.pop(run_id, time.time())
        duration_ms = (time.time() - start_time) * 1000

        logger.error(
            "LLM call failed",
            extra={
                "event": "llm_call",
                "agent": self._name,
                "user_id": self._user_id,
                "run_id": str(run_id),
                "duration_ms": round(duration_ms, 2),
                "error": str(error),
                "error_type": type(error).__name__,
            }
        )
