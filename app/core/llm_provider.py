from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.core.callbacks.logging_handler import LoggingCallbackHandler
import app.core.config as config_module


from langchain_core.runnables import ConfigurableField

from langchain_core.messages.ai import AIMessageChunk
from langchain_core.outputs import ChatResult
from pydantic import BaseModel

class ReasoningChatOpenAI(ChatOpenAI):
    """ChatOpenAI extension that extracts OpenRouter/OpenAI reasoning tokens into message additional_kwargs."""

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ):
        gen_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if gen_chunk and isinstance(gen_chunk.message, AIMessageChunk):
            choices = chunk.get("choices", []) or chunk.get("chunk", {}).get("choices", [])
            if choices and choices[0].get("delta"):
                delta = choices[0]["delta"]
                reasoning = delta.get("reasoning") or delta.get("reasoning_content")
                if reasoning:
                    gen_chunk.message.additional_kwargs["reasoning_content"] = reasoning
                if "reasoning_details" in delta:
                    gen_chunk.message.additional_kwargs["reasoning_details"] = delta["reasoning_details"]
        return gen_chunk

    def _create_chat_result(self, response: dict | BaseModel) -> ChatResult:
        result = super()._create_chat_result(response)
        choices = response.get("choices", []) if isinstance(response, dict) else getattr(response, "choices", [])
        if choices:
            msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else getattr(choices[0], "message", None)
            if msg:
                d = msg if isinstance(msg, dict) else (msg.model_dump() if hasattr(msg, "model_dump") else {})
                reasoning = d.get("reasoning") or d.get("reasoning_content")
                reasoning_details = d.get("reasoning_details")
                for gen in result.generations:
                    if hasattr(gen, "message"):
                        if reasoning:
                            gen.message.additional_kwargs["reasoning_content"] = reasoning
                        if reasoning_details:
                            gen.message.additional_kwargs["reasoning_details"] = reasoning_details
        return result

class LLMFactory:
    @staticmethod
    def get_primary_llm(agent_name: str, user_id: str) -> BaseChatModel:
        s = config_module.setting
        logger = LoggingCallbackHandler(
            agent_name=agent_name,
            user_id=user_id,
        )
        # Using ReasoningChatOpenAI to preserve reasoning tokens
        extra_body = {}
        if s.DO_REASONING_ENABLED:
            extra_body["reasoning"] = {"enabled": True, "effort": s.DO_REASONING_EFFORT}

        base_url = s.DO_BASE_URL.rstrip("/")
        if base_url.endswith("/chat/completions"):
            base_url = base_url[:-len("/chat/completions")]

        return ReasoningChatOpenAI(
            base_url=base_url,
            api_key=s.DO_API_KEY,
            model=s.DO_MODEL,
            temperature=s.TEMPERATURE,
            disable_streaming=False,
            extra_body=extra_body or None,
            callbacks=[logger],
            stream_chunk_timeout=s.LLM_STREAM_CHUNK_TIMEOUT_SECONDS,
        ).configurable_fields(
            openai_api_key=ConfigurableField(
                id="provider_api_key",
                name="Provider API Key",
                description="The API Key for the LLM Provider."
            ),
            model_name=ConfigurableField(
                id="provider_model",
                name="Provider Model",
                description="The Model to use for Inference."
            )
        )

    @staticmethod
    def get_backup_llm(agent_name: str, user_id: str) -> BaseChatModel:
        s = config_module.setting
        logger = LoggingCallbackHandler(
            agent_name=agent_name,
            user_id=user_id,
        )
        base_url = s.OLLAMA_BASE_URL.rstrip("/")
        return ChatOllama(
            base_url=base_url,
            model=s.OLLAMA_MODEL,
            temperature=s.TEMPERATURE,
            disable_streaming="tool_calling",
            callbacks=[logger],
        )

    @classmethod
    def get_llm(cls, agent_name: str = "app", user_id: str = "system") -> BaseChatModel:
        """
        Returns the primary LLM (Digital Ocean) configured with a fallback to the backup (Ollama).
        """
        primary = cls.get_primary_llm(agent_name, user_id)
        backup = cls.get_backup_llm(agent_name, user_id)
        
        # Langchain provides .with_fallbacks for exactly this scenario
        return primary.with_fallbacks([backup])

# Keep backward compatibility if other modules import get_llm directly
def get_llm(agent_name: str = "app", user_id: str = "system") -> BaseChatModel:
    return LLMFactory.get_llm(agent_name, user_id)
