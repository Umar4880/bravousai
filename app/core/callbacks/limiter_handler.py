import logging
import tiktoken

from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from app.utils.limiter import rpm_limier, tpm_limiter

logger = logging.getLogger(__name__)

class RateLimitCallbackHandler(AsyncCallbackHandler):
    """
    Enterprise async callback handler for RPM + TPM rate limiting.
    Hooks directly into LangChain's LLM lifecycle — no signature changes
    to your chains or invoke functions required.
    """

    def __init__(
        self,
        user_id: str,
        model_name: str,
        encoding_name: str = "cl100k_base",  # safe universal fallback
    ):
        self.user_id = user_id
        self.model_name = model_name
        self._encoder = tiktoken.get_encoding(encoding_name)
        self._reserved_tokens: int = 0
        self._rpm_limiter = rpm_limier
        self._tpm_limiter = tpm_limiter

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """
        Fires before the LLM call. We:
        1. Acquire RPM slot
        2. Estimate input tokens and reserve them in TPM
        """
        prompt_text = " ".join(
            msg.content
            for conversation in messages
            for msg in conversation
            if hasattr(msg, "content") and isinstance(msg.content, str)
        )

        self._reserved_tokens = len(self._encoder.encode(prompt_text))

        logger.debug(
            "RateLimitHandler | user=%s | reserved_tokens=%d",
            self.user_id,
            self._reserved_tokens,
        )

        await self._rpm_limiter.acquire(self.user_id)

        await self._tpm_limiter.acquire(self.user_id, weight=self._reserved_tokens)


    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """
        Fires after the LLM responds. Settle actual token usage
        against our reservation. This is the industry-standard
        reserve-then-settle pattern.
        """
        actual_total = 0

        # LangChain surfaces usage in llm_output
        if response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            actual_total = usage.get("total_tokens", 0)

        if actual_total == 0:
            # Fallback: count output tokens ourselves
            for generations in response.generations:
                for gen in generations:
                    if hasattr(gen, "text"):
                        actual_total += len(self._encoder.encode(gen.text))
            actual_total += self._reserved_tokens  # add our input estimate

        extra = actual_total - self._reserved_tokens
        if extra > 0:
            logger.debug(
                "RateLimitHandler | settlement | user=%s | extra_tokens=%d",
                self.user_id,
                extra,
            )
            await self._tpm_limiter.acquire(self.user_id, weight=extra)

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """
        On failure, release the reserved tokens so a failed request
        doesn't permanently consume quota. Critical for production.
        """
        logger.warning(
            "RateLimitHandler | LLM error | user=%s | releasing %d reserved tokens | error=%s",
            self.user_id,
            self._reserved_tokens,
            repr(error),
        )
        await self._tpm_limiter.release(self.user_id, weight=self._reserved_tokens)