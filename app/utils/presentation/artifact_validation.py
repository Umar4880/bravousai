import html
import logging
import re
from dataclasses import dataclass

from app.domain.schemas.agents_schemas.presentation_schema import (
    ArtifactBundle,
    ArtifactSpec,
    ArtifactValidationReport,
)

logger = logging.getLogger(__name__)


class ArtifactValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ArtifactValidationLimits:
    max_html_chars: int = 60_000
    max_css_chars: int = 40_000
    max_js_chars: int = 30_000


FORBIDDEN_HTML_TAGS = ("iframe", "object", "embed", "form")
FORBIDDEN_HTML_RE = re.compile(
    r"<\s*/?\s*(iframe|object|embed|form)\b|<\s*script\b[^>]*\bsrc\s*=",
    re.IGNORECASE,
)
EVENT_HANDLER_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
CSS_EXTERNAL_RE = re.compile(r"@import\b|url\(\s*(['\"]?)\s*(?:https?:|//)", re.IGNORECASE)
JS_FORBIDDEN_PATTERNS = {
    "fetch": re.compile(r"\bfetch\s*\(", re.IGNORECASE),
    "XMLHttpRequest": re.compile(r"\bXMLHttpRequest\b"),
    "WebSocket": re.compile(r"\bWebSocket\b"),
    "EventSource": re.compile(r"\bEventSource\b"),
    "sendBeacon": re.compile(r"\bsendBeacon\s*\(", re.IGNORECASE),
    "document.cookie": re.compile(r"\bdocument\s*\.\s*cookie\b", re.IGNORECASE),
    "localStorage": re.compile(r"\blocalStorage\b"),
    "sessionStorage": re.compile(r"\bsessionStorage\b"),
    "window.parent": re.compile(r"\b(?:window|globalThis|self)\s*\.\s*parent\b"),
    "window.top": re.compile(r"\b(?:window|globalThis|self)\s*\.\s*top\b"),
    "window.opener": re.compile(r"\b(?:window|globalThis|self)\s*\.\s*opener\b"),
    "parent frame access": re.compile(r"(?<![\w$.])parent\s*\.\s*(?:location|document|postMessage)\b"),
    "top frame access": re.compile(r"(?<![\w$.])top\s*\.\s*(?:location|document|postMessage)\b"),
    "opener frame access": re.compile(r"(?<![\w$.])opener\s*\.\s*(?:location|document|postMessage)\b"),
    "eval": re.compile(r"\beval\s*\(", re.IGNORECASE),
    # Case-sensitive: lowercase `function` declarations/IIFEs are allowed.
    "Function": re.compile(r"\bFunction\s*\("),
    "dynamic import": re.compile(r"\bimport\s*\(", re.IGNORECASE),
}


def sanitize_html_body(html_body: str) -> str:
    sanitized = re.sub(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", "", html_body, flags=re.IGNORECASE | re.DOTALL)
    sanitized = EVENT_HANDLER_RE.sub(" data-removed=", sanitized)
    return sanitized.strip()


def validate_artifact_bundle(
    *,
    spec: ArtifactSpec,
    bundle: ArtifactBundle,
    allowed_citation_ids: set[str],
    limits: ArtifactValidationLimits | None = None,
) -> tuple[ArtifactBundle, ArtifactValidationReport]:
    limits = limits or ArtifactValidationLimits()
    warnings: list[str] = []

    if len(bundle.html_body) > limits.max_html_chars:
        raise ArtifactValidationError("HTML body exceeds configured size limit.")
    if len(bundle.css) > limits.max_css_chars:
        raise ArtifactValidationError("CSS exceeds configured size limit.")
    if bundle.javascript and len(bundle.javascript) > limits.max_js_chars:
        raise ArtifactValidationError("JavaScript exceeds configured size limit.")

    sanitized_html = sanitize_html_body(bundle.html_body)
    if sanitized_html != bundle.html_body.strip():
        warnings.append("HTML was sanitized.")

    if FORBIDDEN_HTML_RE.search(sanitized_html):
        forbidden = ", ".join(FORBIDDEN_HTML_TAGS)
        raise ArtifactValidationError(f"HTML contains forbidden tags or external scripts: {forbidden}.")

    # We allow CSS external imports (like Google Fonts) for hybrid_article styling.
    # if CSS_EXTERNAL_RE.search(bundle.css):
    #     raise ArtifactValidationError("CSS contains @import or an external url(...).")

    javascript = (bundle.javascript or "").strip() or None
    if javascript:
        for label, pattern in JS_FORBIDDEN_PATTERNS.items():
            match = pattern.search(javascript)
            if match:
                logger.warning(
                    "Artifact JavaScript rejected | capability=%s | fragment=%s",
                    label,
                    _diagnostic_fragment(javascript, match.start(), match.end()),
                )
                raise ArtifactValidationError(f"JavaScript contains forbidden capability: {label}.")

    unknown_ids = sorted(set(spec.citation_ids) - allowed_citation_ids)
    if unknown_ids:
        raise ArtifactValidationError(f"Artifact cites unknown evidence IDs: {', '.join(unknown_ids)}.")

    invented_url_ids = _citation_ids_from_urls(sanitized_html) - allowed_citation_ids
    if invented_url_ids:
        raise ArtifactValidationError(f"Artifact contains unapproved citation URLs: {', '.join(sorted(invented_url_ids))}.")

    return (
        ArtifactBundle(
            html_body=sanitized_html,
            css=bundle.css.strip(),
            javascript=javascript,
        ),
        ArtifactValidationReport(
            html_ok=True,
            css_ok=True,
            javascript_ok=True,
            citations_ok=True,
            sanitized=bool(warnings),
            warnings=warnings,
        ),
    )


def render_standalone_html(*, bundle: ArtifactBundle, title: str, nonce: str) -> str:
    safe_title = html.escape(title or "Research artifact")
    resize_script = (
        f'<script nonce="{html.escape(nonce)}">\n'
        "(function(){\n"
        "  function height(){\n"
        "    var body = document.body;\n"
        "    var doc = document.documentElement;\n"
        "    return Math.max(body ? body.scrollHeight : 0, body ? body.offsetHeight : 0, doc.scrollHeight, doc.offsetHeight);\n"
        "  }\n"
        "  function report(){\n"
        "    window.parent.postMessage({ type: 'artifact:height', height: height() }, '*');\n"
        "  }\n"
        "  window.addEventListener('load', report);\n"
        "  if ('ResizeObserver' in window) {\n"
        "    new ResizeObserver(report).observe(document.documentElement);\n"
        "  }\n"
        "  setTimeout(report, 50);\n"
        "  setTimeout(report, 300);\n"
        "})();\n"
        "</script>"
    )
    script = ""
    if bundle.javascript:
        script = f'<script nonce="{html.escape(nonce)}">\n{bundle.javascript}\n</script>'
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{safe_title}</title>\n"
        f"<style>\n{bundle.css}\n</style>\n"
        "</head>\n"
        f"<body>\n{bundle.html_body}\n{script}\n{resize_script}\n</body>\n"
        "</html>\n"
    )


def csp_header(nonce: str) -> str:
    return (
        "default-src 'none'; "
        "connect-src 'none'; "
        "object-src 'none'; "
        "frame-src 'none'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "img-src data:; "
        "style-src 'unsafe-inline'; "
        f"script-src 'nonce-{nonce}';"
    )


def _citation_ids_from_urls(html_body: str) -> set[str]:
    # Only URLs in explicit data-citation-id attributes can represent approved
    # citation links. Any normal external href remains inert text in the sandbox.
    matches = re.findall(r'data-citation-id=["\']([^"\']+)["\']', html_body, flags=re.IGNORECASE)
    return {match.strip() for match in matches if match.strip()}


def _diagnostic_fragment(text: str, start: int, end: int, *, radius: int = 36) -> str:
    fragment = text[max(0, start - radius) : min(len(text), end + radius)]
    return " ".join(fragment.split())
