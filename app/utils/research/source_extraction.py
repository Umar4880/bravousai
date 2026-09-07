from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import io
import re
from typing import Callable
from urllib.parse import urljoin

import httpx

from app.domain.schemas.agents_schemas.search_result_schema import SearchResult
from app.domain.schemas.agents_schemas.source_extraction_schema import ExtractedSource, SourceExtractionBudget
from app.utils.research.url_safety import URLSafetyError, validate_url_for_fetch


class ReadableHTMLParser(HTMLParser):
    """Minimal readable-text parser that ignores page chrome and scripts."""

    def __init__(self) -> None:
        """Initialize parser state for readable text extraction."""
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        """Track ignored sections and add spacing around block-like tags."""
        if tag in {"script", "style", "nav", "footer", "header", "aside", "noscript", "svg"}:
            self._skip_stack.append(tag)
        if tag in {"p", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """Resume collection after ignored sections and add block spacing."""
        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()
        if tag in {"p", "li", "tr", "section", "article"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        """Collect visible text chunks when not inside an ignored section."""
        if not self._skip_stack:
            self.parts.append(data)

    def text(self) -> str:
        """Return collected text with normalized whitespace."""
        return normalize_whitespace(" ".join(self.parts))


async def extract_selected_sources(
    search_results: list[SearchResult],
    selected_result_ids: list[str],
    *,
    budget: SourceExtractionBudget,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> dict[str, ExtractedSource]:
    """Extract a bounded set of selected search results with custom HTTP fetches.

    This deterministic Phase D extractor runs concurrent safe fetches, keeps
    selected IDs stable, and returns failed placeholders instead of crashing the
    research workflow when an ID or fetch fails.
    """
    by_id = {result.result_id: result for result in search_results}
    semaphore = asyncio.Semaphore(budget.max_concurrent_fetches)

    async def run_one(result_id: str) -> tuple[str, ExtractedSource]:
        async with semaphore:
            result = by_id.get(result_id)
            if result is None:
                return result_id, _failed_placeholder(result_id, "Selected result ID was not found.")
            return result_id, await extract_source(result, budget=budget, client_factory=client_factory)

    pairs = await asyncio.gather(*(run_one(result_id) for result_id in selected_result_ids))
    return dict(pairs)


async def extract_source(
    search_result: SearchResult,
    *,
    budget: SourceExtractionBudget,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> ExtractedSource:
    """Safely fetch and clean one source using the custom HTTP extractor.

    The function validates URL safety before and after redirects, enforces
    timeout and response-size limits, extracts HTML or optional PDF text, and
    falls back to the snippet when extraction is unavailable.
    """
    try:
        validate_url_for_fetch(search_result.url)
    except URLSafetyError as exc:
        return _fallback_result(search_result, "failed", "unknown", str(exc))

    try:
        response = await _fetch_with_redirects(search_result.url, budget=budget, client_factory=client_factory)
    except Exception as exc:
        return _fallback_result(search_result, "failed", "unknown", str(exc))

    content_type_header = response.headers.get("content-type", "").lower()
    content_type = detect_content_type(search_result.url, content_type_header)
    if response.status_code >= 400:
        return _fallback_result(search_result, "failed", content_type, f"HTTP {response.status_code}.")

    max_bytes = budget.max_pdf_bytes if content_type == "pdf" else budget.max_html_bytes
    if len(response.content) > max_bytes:
        return _fallback_result(search_result, "failed", content_type, "Response body exceeded byte limit.")

    try:
        if content_type == "html":
            text = extract_html_text(response.text)
        elif content_type == "text":
            text = normalize_whitespace(response.text)
        elif content_type == "pdf":
            text = extract_pdf_text(response.content)
        else:
            return _fallback_result(search_result, "skipped", "unknown", f"Unsupported content type: {content_type_header}.")
    except Exception as exc:
        return _fallback_result(search_result, "failed", content_type, str(exc))

    if not text:
        return _fallback_result(search_result, "failed", content_type, "Extracted text was empty.")

    truncated = len(text) > budget.max_chars_per_source
    cleaned_text = text[: budget.max_chars_per_source].rstrip() if truncated else text
    return ExtractedSource(
        result_id=search_result.result_id,
        title=search_result.title,
        url=search_result.url,
        content_type=content_type,
        extraction_status="partial" if truncated else "success",
        cleaned_text=cleaned_text,
        char_count=len(cleaned_text),
        truncated=truncated,
        snippet_fallback_used=False,
        content_hash=sha256(cleaned_text.encode("utf-8")).hexdigest(),
    )


async def _fetch_with_redirects(
    url: str,
    *,
    budget: SourceExtractionBudget,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> httpx.Response:
    """Fetch a URL while validating every redirect destination."""
    factory = client_factory or (
        lambda: httpx.AsyncClient(
            timeout=budget.request_timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "BravousResearchBot/1.0"},
        )
    )
    current_url = url
    async with factory() as client:
        for _ in range(budget.max_redirects + 1):
            validate_url_for_fetch(current_url)
            response = await client.get(current_url)
            if response.status_code not in {301, 302, 303, 307, 308}:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            current_url = urljoin(current_url, location)
        raise URLSafetyError("Redirect limit exceeded.")


def detect_content_type(url: str, content_type_header: str) -> str:
    """Classify fetched content as PDF, HTML, text, or unsupported."""
    lower_url = (url or "").lower()
    if "pdf" in content_type_header or lower_url.endswith(".pdf"):
        return "pdf"
    if "html" in content_type_header:
        return "html"
    if content_type_header.startswith("text/plain") or "text/plain" in content_type_header:
        return "text"
    return "unknown"


def extract_html_text(html: str) -> str:
    """Extract normalized readable text from an HTML document."""
    parser = ReadableHTMLParser()
    parser.feed(html or "")
    return parser.text()


def extract_pdf_text(content: bytes) -> str:
    """Extract text from PDF bytes when optional pypdf support is installed."""
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PDF extraction dependency is unavailable.") from exc

    reader = PdfReader(io.BytesIO(content))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return normalize_whitespace(" ".join(parts))


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace and trim surrounding space."""
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def _fallback_result(
    search_result: SearchResult,
    status: str,
    content_type: str,
    error_message: str,
) -> ExtractedSource:
    """Build an ExtractedSource that clearly labels snippet fallback usage."""
    fallback = normalize_whitespace(search_result.snippet)
    return ExtractedSource(
        result_id=search_result.result_id,
        title=search_result.title,
        url=search_result.url,
        content_type=content_type,  # type: ignore[arg-type]
        extraction_status=status,  # type: ignore[arg-type]
        cleaned_text=fallback,
        extracted_at=datetime.now(timezone.utc),
        char_count=len(fallback),
        truncated=False,
        snippet_fallback_used=True,
        error_message=error_message,
    )


def _failed_placeholder(result_id: str, error_message: str) -> ExtractedSource:
    """Return a failed extraction placeholder for unknown or invalid IDs."""
    return ExtractedSource(
        result_id=result_id,
        title="",
        url="",
        extraction_status="failed",
        cleaned_text="",
        char_count=0,
        truncated=False,
        snippet_fallback_used=True,
        error_message=error_message,
    )
