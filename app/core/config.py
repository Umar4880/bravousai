from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from pathlib import Path
import os
import sys

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Setting(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        extra="ignore",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    APP_NAME: str = "Bravous Research Agent"
    ENV: Literal["prod", "dev", "staging"] = "dev"
    DEBUG: bool = False

    REDIS_URL: str = ""
    APP_DATABASE_URL: str = ""
    CHECKPOINT_DATABASE_URL: str = ""

    TAVILY_API_KEY: str = ""

    OLLAMA_BASE_URL: str = ""
    OLLAMA_MODEL: str = "llama3.2:latest"
    TEMPERATURE: float = 0.2

    DO_BASE_URL: str = ""
    DO_API_KEY: str = ""
    DO_MODEL: str = ""
    DO_REASONING_ENABLED: bool = False
    DO_REASONING_EFFORT: Literal["low", "medium", "high"] = "low"

    ALLOWED_ORIGINS: str = "*"

    OBJECT_STORAGE_ENDPOINT: str = "http://localhost:9000"
    OBJECT_STORAGE_ACCESS_KEY: str = "minioadmin"
    OBJECT_STORAGE_SECRET_KEY: str = "minioadmin123"
    OBJECT_STORAGE_REGION: str = "us-east-1"
    OBJECT_STORAGE_BUCKET_PROJECT_FILES: str = "project-files"
    OBJECT_STORAGE_SECURE: bool = False
    MAX_UPLOAD_BYTES: int = 25_000_000

    RESEARCH_MAX_FOLLOW_UP_ITERATIONS: int = 1
    RESEARCH_MAX_FOLLOW_UP_QUERIES_TOTAL: int = 3
    RESEARCH_MAX_FOLLOW_UP_QUERIES_PER_ITERATION: int = 3
    RESEARCH_MAX_RESULTS_PER_QUERY: int = 5
    RESEARCH_MAX_ADDITIONAL_RAW_RESULTS: int = 15
    RESEARCH_PLAN_TIMEOUT_SECONDS: int = 60
    RESEARCH_SYNTHESIS_TIMEOUT_SECONDS: int = 420
    RESEARCH_SYNTHESIS_MAX_RAW_RESULTS: int = 20
    RESEARCH_PACKAGE_VALIDATION_TIMEOUT_SECONDS: int = 20
    RESEARCH_EVENT_DISPATCH_TIMEOUT_SECONDS: int = 5
    RESEARCH_MAX_CANDIDATE_EVIDENCE_NOTES_PER_CLAIM: int = 5
    RESEARCH_MAX_CLAIMS_PER_CLASSIFICATION_BATCH: int = 15
    RESEARCH_MAX_CLAIMS_PER_SEMANTIC_VERIFICATION_BATCH: int = 12
    
    RESEARCH_MAX_REFINEMENT_ITERATIONS: int = 2
    RESEARCH_MIN_RICH_SOURCES: int = 3
    RESEARCH_COVERAGE_THRESHOLD: float = 0.8
    RESEARCH_GAP_ANALYSIS_TIMEOUT_SECONDS: int = 30
    RESEARCH_RELEVANCE_JUDGE_TIMEOUT_SECONDS: int = 45
    RESEARCH_PREFER_DOMAIN_RELEVANCE_BOOST: float = 0.15

    # ── Context Management Budgets ──────────────────────────────────
    # Per-file character cap for extracted_text injected into prompts.
    CONTEXT_MAX_FILE_TEXT_CHARS: int = 8000
    # Sliding window: max messages kept when injecting chat history.
    CONTEXT_MAX_HISTORY_MESSAGES: int = 20
    # Max past workflow plans passed to the supervisor prompt.
    CONTEXT_MAX_SUPERVISOR_PLANS: int = 3
    # Max entries in conversation_index passed to agents.
    CONTEXT_MAX_CONVERSATION_INDEX: int = 20
    # Per-source char cap applied before synthesis LLM call.
    CONTEXT_MAX_CHARS_PER_SOURCE_SYNTHESIS: int = 5000
    # Total char budget for all merged_sources in synthesis payload.
    CONTEXT_MAX_TOTAL_SYNTHESIS_CHARS: int = 60000

    # Per-chunk streaming timeout for the LLM provider.
    # None (default) disables the per-chunk guard and relies solely on the
    # outer asyncio.wait_for timeout in each node (synthesis, planner, writer).
    # Setting this too low (e.g. 120s) causes premature stream cancellation on
    # slow/large responses from reasoning models like deepseek.
    LLM_STREAM_CHUNK_TIMEOUT_SECONDS: float | None = None

    WRITER_TIMEOUT_SECONDS: int = 180
    OBSERVER_TIMEOUT_SECONDS: int = 60
    ARTIFACT_MAX_HTML_CHARS: int = 60_000
    ARTIFACT_MAX_CSS_CHARS: int = 40_000
    ARTIFACT_MAX_JS_CHARS: int = 30_000

    SOURCE_EXTRACTION_MAX_SELECTED_SOURCES_TOTAL: int = 8
    SOURCE_EXTRACTION_MAX_NEW_SOURCES_AFTER_FOLLOW_UP: int = 3
    SOURCE_EXTRACTION_MAX_SOURCES_PER_DOMAIN: int = 2
    SOURCE_EXTRACTION_MAX_CONCURRENT_FETCHES: int = 4
    SOURCE_EXTRACTION_REQUEST_TIMEOUT_SECONDS: float = 8.0
    SOURCE_EXTRACTION_MAX_REDIRECTS: int = 3
    SOURCE_EXTRACTION_MAX_HTML_BYTES: int = 1_500_000
    SOURCE_EXTRACTION_MAX_PDF_BYTES: int = 5_000_000
    SOURCE_EXTRACTION_MAX_CHARS_PER_SOURCE: int = 12_000
    SOURCE_EXTRACTION_MAX_TOTAL_CLEANED_CHARS: int = 80_000
    SOURCE_ENRICHMENT_MAX_CANDIDATES_FOR_LLM_PLANNER: int = 16
    SOURCE_ENRICHMENT_MAX_TAVILY_BASIC_URLS_TOTAL: int = 8
    SOURCE_ENRICHMENT_MAX_ADVANCED_RETRIES_TOTAL: int = 2
    SOURCE_ENRICHMENT_MAX_CUSTOM_FALLBACK_URLS_TOTAL: int = 3
    SOURCE_ENRICHMENT_TAVILY_CHUNKS_PER_SOURCE: int = 3
    TAVILY_EXTRACT_TIMEOUT_SECONDS: float = 15.0
    SOURCE_ENRICHMENT_ALLOW_SNIPPET_ONLY_EXTRACTION_OVERRIDE: bool = False

    LANGSMITH_TRACING: str = ""
    LANGSMITH_ENDPOINT: str = ""
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = ""

    @property
    def CHECKPOINT_CONN_STRING(self) -> str:
        # Backward-compatible alias for older references.
        return self.CHECKPOINT_DATABASE_URL

setting = Setting()


def reload_setting() -> Setting:
    global setting
    setting = Setting()
    return setting


def configure_langsmith_environment() -> None:
    if "unittest" in sys.modules or any(part == "unittest" for part in Path(sys.argv[0]).parts):
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ.pop("LANGCHAIN_API_KEY", None)
        return

    values = {
        "LANGSMITH_TRACING": setting.LANGSMITH_TRACING,
        "LANGSMITH_ENDPOINT": setting.LANGSMITH_ENDPOINT,
        "LANGSMITH_API_KEY": setting.LANGSMITH_API_KEY,
        "LANGSMITH_PROJECT": setting.LANGSMITH_PROJECT,
    }

    for key, value in values.items():
        if value:
            os.environ[key] = value

    if setting.LANGSMITH_TRACING and not os.environ.get("LANGCHAIN_TRACING_V2"):
        os.environ["LANGCHAIN_TRACING_V2"] = setting.LANGSMITH_TRACING
    if setting.LANGSMITH_PROJECT and not os.environ.get("LANGCHAIN_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = setting.LANGSMITH_PROJECT
    if setting.LANGSMITH_API_KEY and not os.environ.get("LANGCHAIN_API_KEY"):
        os.environ["LANGCHAIN_API_KEY"] = setting.LANGSMITH_API_KEY
    if setting.LANGSMITH_ENDPOINT and not os.environ.get("LANGCHAIN_ENDPOINT"):
        os.environ["LANGCHAIN_ENDPOINT"] = setting.LANGSMITH_ENDPOINT


# configure_langsmith_environment()
