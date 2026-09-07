import unittest

from app.utils.citation_validation import (
    CitationValidationError,
    extract_citation_ids,
    repair_citation_markers,
    validate_citation_markers,
)


class CitationValidationTests(unittest.TestCase):
    def test_valid_citation_marker_passes(self):
        self.assertEqual(validate_citation_markers("Claim. [[cite:sr_1]]", {"sr_1"}), ["sr_1"])

    def test_unknown_result_id_fails(self):
        with self.assertRaises(CitationValidationError):
            validate_citation_markers("Claim. [[cite:missing]]", {"sr_1"})

    def test_malformed_citation_marker_fails(self):
        with self.assertRaises(CitationValidationError):
            validate_citation_markers("Claim. [[cite sr_1]]", {"sr_1"})

    def test_multiple_valid_citations_pass(self):
        markdown = "First. [[cite:sr_1]] Second. [[cite:sr_2]]"

        self.assertEqual(validate_citation_markers(markdown, {"sr_1", "sr_2"}), ["sr_1", "sr_2"])
        self.assertEqual(extract_citation_ids(markdown), ["sr_1", "sr_2"])

    def test_repair_removes_unknown_and_malformed_markers(self):
        markdown = "Good [[cite:sr_1]] Bad [[cite:sr_xxxx]] Broken [[cite sr_2]]"

        repaired, removed = repair_citation_markers(markdown, {"sr_1"})

        self.assertEqual(validate_citation_markers(repaired, {"sr_1"}), ["sr_1"])
        self.assertIn("[[cite:sr_xxxx]]", removed)
        self.assertIn("[[cite sr_2]]", removed)
        self.assertNotIn("sr_xxxx", repaired)


if __name__ == "__main__":
    unittest.main()
