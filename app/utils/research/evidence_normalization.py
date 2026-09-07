from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "gbraid",
    "wbraid",
    "mc_cid",
    "mc_eid",
}


@dataclass(frozen=True)
class SourceQualityConfig:
    official_domains: set[str] = field(
        default_factory=lambda: {
            "gov",
            "edu",
            "who.int",
            "un.org",
            "worldbank.org",
            "sec.gov",
            "federalreserve.gov",
            "bls.gov",
        }
    )
    reputable_domains: set[str] = field(
        default_factory=lambda: {
            "reuters.com",
            "apnews.com",
            "cnbc.com",
            "ft.com",
            "tradingeconomics.com",
            "bbc.com",
            "bbc.co.uk",
            "nature.com",
            "science.org",
            "statista.com",
        }
    )
    financial_domains: set[str] = field(
        default_factory=lambda: {
            "bloomberg.com", "wsj.com", "ft.com", "barrons.com",
            "marketwatch.com", "investing.com",
            "fred.stlouisfed.org", "dallasfed.org", "newyorkfed.org",
            "ecb.europa.eu", "bis.org", "imf.org",
            "jpmorgan.com", "goldmansachs.com", "morganstanley.com",
            "franklintempleton.com", "pimco.com", "blackrock.com",
            "cmegroup.com", "isda.org", "tradingeconomics.com",
        }
    )
    penalized_domains: set[str] = field(
        default_factory=lambda: {
            "facebook.com",
            "reddit.com",
            "x.com",
            "twitter.com",
            "tiktok.com",
            "youtube.com",
            "instagram.com",
            "pinterest.com",
            "threads.net",
        }
    )
    primary_research_domains: set[str] = field(
        default_factory=lambda: {
            "arxiv.org",
            "aclanthology.org",
        }
    )
    peer_reviewed_domains: set[str] = field(
        default_factory=lambda: {
            "nature.com",
            "science.org",
            "nejm.org",
            "thelancet.com",
        }
    )
    official_documentation_domains: set[str] = field(
        default_factory=lambda: {
            "docs.github.com",
            "docs.python.org",
            "kubernetes.io",
            "cloud.google.com",
            "learn.microsoft.com",
            "docs.aws.amazon.com",
            "platform.openai.com",
        }
    )
    vendor_domains: set[str] = field(
        default_factory=lambda: {
            "openai.com",
            "anthropic.com",
            "google.com",
            "microsoft.com",
            "amazon.com",
            "nvidia.com",
        }
    )
    community_domains: set[str] = field(
        default_factory=lambda: {
            "medium.com",
            "dev.to",
            "substack.com",
            "linkedin.com",
        }
    )
    social_domains: set[str] = field(
        default_factory=lambda: {
            "youtube.com",
            "youtu.be",
            "x.com",
            "twitter.com",
            "facebook.com",
            "reddit.com",
            "tiktok.com",
        }
    )
    official_score: float = 1.0
    financial_score: float = 0.90
    reputable_score: float = 0.82
    unknown_score: float = 0.55
    penalized_score: float = 0.25


DEFAULT_SOURCE_QUALITY_CONFIG = SourceQualityConfig()

ARXIV_PATH_PATTERN = re.compile(
    r"^/(?:abs|pdf|html)/(?P<paper_id>(?:\d{4}\.\d{4,5}|[A-Za-z.-]+/\d{7}))(?P<version>v\d+)?(?:\.pdf)?/?$",
    re.IGNORECASE,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def extract_domain(url: str | None) -> str:
    if not url:
        return ""

    try:
        parsed = urlsplit(url if "://" in url else f"https://{url}")
    except ValueError:
        return ""

    hostname = (parsed.hostname or "").lower().strip(".")
    if not _is_valid_hostname(hostname):
        return ""
    if hostname.startswith("www."):
        return hostname[4:]
    return hostname


def normalize_url(url: str | None) -> str:
    if not url:
        return ""

    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return ""

    if not parsed.scheme and not parsed.netloc:
        parsed = urlsplit(f"https://{url.strip()}")

    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").lower().strip(".")
    if not _is_valid_hostname(hostname):
        return ""

    netloc = hostname
    if parsed.port and not (
        (scheme == "http" and parsed.port == 80)
        or (scheme == "https" and parsed.port == 443)
    ):
        netloc = f"{netloc}:{parsed.port}"

    path = parsed.path or ""
    if path != "/":
        path = path.rstrip("/")
    else:
        path = ""

    filtered_params = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lower_key = key.lower()
        if lower_key in TRACKING_QUERY_PARAMS:
            continue
        if any(lower_key.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        filtered_params.append((key, value))

    query = urlencode(sorted(filtered_params), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def generate_result_id(normalized_url: str) -> str:
    digest = sha256(normalized_url.encode("utf-8")).hexdigest()[:16]
    return f"sr_{digest}"


def extract_scholarly_identifier(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None

    domain = extract_domain(url)
    if domain == "arxiv.org":
        match = ARXIV_PATH_PATTERN.match(parsed.path or "")
        if match:
            return f"arxiv:{match.group('paper_id').lower()}"
    if domain == "aclanthology.org":
        path = (parsed.path or "").strip("/")
        if path:
            return f"acl:{path.removesuffix('.pdf').lower()}"
    return None


def _extract_arxiv_version(url: str | None) -> int:
    if not url:
        return 0
    try:
        parsed = urlsplit(url)
    except ValueError:
        return 0
    if extract_domain(url) != "arxiv.org":
        return 0
    match = ARXIV_PATH_PATTERN.match(parsed.path or "")
    if not match:
        return 0
    version = match.group("version") or ""
    if version.startswith("v") and version[1:].isdigit():
        return int(version[1:])
    return 0


def parse_publication_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    formats = (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    )
    for date_format in formats:
        try:
            return datetime.strptime(text, date_format).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def score_freshness(
    published_at: datetime | None,
    *,
    now: datetime | None = None,
    missing_score: float = 0.45,
) -> float:
    if published_at is None:
        return missing_score

    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    age_days = max((current - published_at).days, 0)
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.9
    if age_days <= 90:
        return 0.75
    if age_days <= 365:
        return 0.55
    if age_days <= 1095:
        return 0.35
    return 0.2


def _domain_matches(domain: str, configured_domain: str) -> bool:
    configured = configured_domain.lower().strip(".")
    domain = domain.lower().strip(".")
    return domain == configured or domain.endswith(f".{configured}")


def _is_valid_hostname(hostname: str) -> bool:
    if not hostname or " " in hostname or "." not in hostname:
        return False
    labels = hostname.split(".")
    return all(label and len(label) <= 63 for label in labels)


def score_source_quality(
    domain: str | None,
    *,
    config: SourceQualityConfig = DEFAULT_SOURCE_QUALITY_CONFIG,
) -> float:
    domain = (domain or "").lower().strip(".")
    if not domain:
        return config.unknown_score

    if any(_domain_matches(domain, value) for value in config.official_domains):
        return config.official_score
    if any(_domain_matches(domain, value) for value in config.financial_domains):
        return config.financial_score
    if any(_domain_matches(domain, value) for value in config.reputable_domains):
        return config.reputable_score
    if any(_domain_matches(domain, value) for value in config.penalized_domains):
        return config.penalized_score
    return config.unknown_score


def classify_source_type(
    domain: str | None,
    *,
    config: SourceQualityConfig = DEFAULT_SOURCE_QUALITY_CONFIG,
) -> str:
    domain = (domain or "").lower().strip(".")
    if not domain:
        return "unknown"

    if any(_domain_matches(domain, value) for value in config.penalized_domains):
        return "penalized"
    if any(_domain_matches(domain, value) for value in config.social_domains):
        return "social"
    if any(_domain_matches(domain, value) for value in config.community_domains):
        return "community"
    if any(_domain_matches(domain, value) for value in config.official_documentation_domains):
        return "official_documentation"
    if any(_domain_matches(domain, value) for value in config.primary_research_domains):
        return "primary_research"
    if any(_domain_matches(domain, value) for value in config.peer_reviewed_domains):
        return "peer_reviewed"
    if any(_domain_matches(domain, value) for value in config.official_domains):
        return "official"
    if any(_domain_matches(domain, value) for value in config.financial_domains):
        return "financial"
    if any(_domain_matches(domain, value) for value in config.reputable_domains):
        return "reputable_editorial"
    if any(_domain_matches(domain, value) for value in config.vendor_domains):
        return "vendor"
    return "unknown"


def duplicate_group_id_for_url(normalized_url: str) -> str | None:
    if not normalized_url:
        return None
    return f"dup_{sha256(normalized_url.encode('utf-8')).hexdigest()[:16]}"


def build_normalized_result_fields(
    *,
    query: str,
    title: str | None,
    url: str | None,
    snippet: str | None,
    source: str | None = None,
    published_at: Any = None,
    relevance_score: float | None = None,
    retrieved_at: datetime | None = None,
    config: SourceQualityConfig = DEFAULT_SOURCE_QUALITY_CONFIG,
) -> dict[str, Any]:
    normalized = normalize_url(url)
    domain = extract_domain(normalized)
    parsed_published_at = parse_publication_date(published_at)
    scholarly_identifier = extract_scholarly_identifier(normalized)
    evidence_key = scholarly_identifier or normalized

    return {
        "result_id": generate_result_id(evidence_key),
        "query": query,
        "matched_queries": [query] if query else [],
        "title": title or "",
        "url": url or "",
        "normalized_url": normalized,
        "domain": domain,
        "source": source,
        "published_at": parsed_published_at,
        "retrieved_at": retrieved_at or utc_now(),
        "snippet": snippet or "",
        "relevance_score": relevance_score,
        "source_quality_score": score_source_quality(domain, config=config),
        "source_type": classify_source_type(domain, config=config),
        "freshness_score": score_freshness(parsed_published_at, now=retrieved_at),
        "duplicate_group_id": None,
        "scholarly_identifier": scholarly_identifier,
        "published_date": published_at,
        "relevance": _legacy_relevance_label(relevance_score),
    }


def deduplicate_result_dicts(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}

    for result in results:
        normalized_url = result.get("normalized_url") or normalize_url(result.get("url"))
        result["normalized_url"] = normalized_url
        scholarly_identifier = result.get("scholarly_identifier") or extract_scholarly_identifier(normalized_url)
        result["scholarly_identifier"] = scholarly_identifier
        dedupe_key = scholarly_identifier or normalized_url

        if not dedupe_key:
            unique_key = f"{result.get('result_id') or ''}:{len(by_url)}"
            by_url[unique_key] = result
            continue

        group_id = duplicate_group_id_for_url(dedupe_key)
        existing = by_url.get(dedupe_key)
        if existing is None:
            result["duplicate_group_id"] = group_id
            result["result_id"] = generate_result_id(dedupe_key)
            by_url[dedupe_key] = result
            continue

        existing["duplicate_group_id"] = group_id
        existing_queries = list(existing.get("matched_queries") or [])
        for query in result.get("matched_queries") or [result.get("query")]:
            if query and query not in existing_queries:
                existing_queries.append(query)
        existing["matched_queries"] = existing_queries

        if _result_rank(result) > _result_rank(existing):
            result["duplicate_group_id"] = group_id
            result["matched_queries"] = existing_queries
            result["result_id"] = generate_result_id(dedupe_key)
            by_url[dedupe_key] = result

    return list(by_url.values())


def _result_rank(result: dict[str, Any]) -> tuple[float, float, float, float, int]:
    return (
        float(_extract_arxiv_version(result.get("normalized_url"))),
        float(result.get("source_quality_score") or 0),
        float(result.get("freshness_score") or 0),
        float(result.get("relevance_score") or 0),
        len(result.get("snippet") or ""),
    )


def _legacy_relevance_label(relevance_score: float | None) -> str | None:
    if relevance_score is None:
        return None
    return "high" if relevance_score > 0.7 else "medium"
