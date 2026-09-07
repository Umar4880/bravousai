from datetime import datetime, timezone
import unittest

from app.utils.evidence_normalization import (
    SourceQualityConfig,
    build_normalized_result_fields,
    deduplicate_result_dicts,
    extract_domain,
    generate_result_id,
    normalize_url,
    parse_publication_date,
    score_freshness,
    score_source_quality,
)


class EvidenceNormalizationTests(unittest.TestCase):
    def test_url_normalization_removes_tracking_parameters_and_fragments(self):
        url = "HTTPS://Example.com/Article/?utm_source=news&b=2&a=1&fbclid=abc#section"

        self.assertEqual(normalize_url(url), "https://example.com/Article?a=1&b=2")


    def test_url_normalization_preserves_meaningful_query_parameters(self):
        url = "https://example.com/search?q=ai&page=2&utm_campaign=test"

        self.assertEqual(normalize_url(url), "https://example.com/search?page=2&q=ai")


    def test_equivalent_urls_normalize_identically(self):
        first = "https://EXAMPLE.com/news/?b=2&a=1&utm_medium=social#comments"
        second = "https://example.com/news?a=1&b=2"

        self.assertEqual(normalize_url(first), normalize_url(second))


    def test_stable_ids_match_for_equivalent_urls_and_differ_for_distinct_urls(self):
        first = generate_result_id(normalize_url("https://example.com/news/?utm_source=x"))
        second = generate_result_id(normalize_url("https://example.com/news"))
        third = generate_result_id(normalize_url("https://example.com/news?id=123"))

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)


    def test_domain_extraction_handles_subdomains_and_invalid_urls(self):
        self.assertEqual(extract_domain("https://sub.example.com/path"), "sub.example.com")
        self.assertEqual(extract_domain("not a url"), "")


    def test_deduplication_groups_duplicates_retains_canonical_and_query_provenance(self):
        first = build_normalized_result_fields(
            query="query one",
            title="First",
            url="https://example.com/article?utm_source=x",
            snippet="Short",
            relevance_score=0.5,
        )
        second = build_normalized_result_fields(
            query="query two",
            title="Second",
            url="https://example.com/article",
            snippet="Longer snippet",
            relevance_score=0.9,
        )

        deduplicated = deduplicate_result_dicts([first, second])

        self.assertEqual(len(deduplicated), 1)
        self.assertIsNotNone(deduplicated[0]["duplicate_group_id"])
        self.assertEqual(deduplicated[0]["title"], "Second")
        self.assertEqual(deduplicated[0]["matched_queries"], ["query one", "query two"])


    def test_freshness_scores_recent_sources_higher_than_stale_sources(self):
        now = datetime(2026, 6, 6, tzinfo=timezone.utc)
        recent = datetime(2026, 6, 1, tzinfo=timezone.utc)
        stale = datetime(2020, 1, 1, tzinfo=timezone.utc)

        self.assertGreater(score_freshness(recent, now=now), score_freshness(stale, now=now))


    def test_freshness_missing_publication_date_is_safe(self):
        self.assertEqual(score_freshness(None), 0.45)


    def test_publication_date_parsing_accepts_common_formats(self):
        parsed = parse_publication_date("June 6, 2026")

        self.assertEqual(parsed, datetime(2026, 6, 6, tzinfo=timezone.utc))


    def test_source_quality_ordering_is_configurable(self):
        config = SourceQualityConfig(
            official_domains={"official.example"},
            reputable_domains={"reputable.example"},
            penalized_domains={"low.example"},
        )

        official = score_source_quality("api.official.example", config=config)
        reputable = score_source_quality("reputable.example", config=config)
        unknown = score_source_quality("unknown.example", config=config)
        penalized = score_source_quality("low.example", config=config)

        self.assertGreater(official, reputable)
        self.assertGreater(reputable, unknown)
        self.assertGreater(unknown, penalized)


if __name__ == "__main__":
    unittest.main()
