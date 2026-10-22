import unittest

from build_crosswalk import CROSSWALK_END, CROSSWALK_START, SpanError, _splice_readme

ROWS = [
    {
        "soc2_cc": "CC1.1",
        "nist_800_53": "AC-1",
        "iso_27001_2022": "A.5.1",
        "confidence": "Strong",
        "rationale": "alpha",
    }
]
CANONICAL_ROW = "| CC1.1 | AC-1 | A.5.1 | Strong | alpha |"
STALE_BODY = "| CC1.1 | AC-9 | A.5.1 | Strong | alpha |\n"


def host(body: str) -> str:
    return f"HEAD\n{CROSSWALK_START}\n{body}{CROSSWALK_END}\nTAIL\n"


class ReadmeSpanTests(unittest.TestCase):
    def test_stale_span_is_replaced_and_prose_stays(self):
        updated = _splice_readme(host(STALE_BODY), ROWS)

        self.assertIn(CANONICAL_ROW, updated)
        self.assertNotIn("AC-9", updated)
        self.assertTrue(updated.startswith("HEAD\n"))
        self.assertTrue(updated.endswith("TAIL\n"))

    def test_splice_is_idempotent(self):
        once = _splice_readme(host(STALE_BODY), ROWS)
        twice = _splice_readme(once, ROWS)

        self.assertEqual(twice, once)

    def test_missing_start_marker(self):
        with self.assertRaises(SpanError) as caught:
            _splice_readme("HEAD\nTAIL\n", ROWS)

        self.assertIn("CROSSWALK:START marker is missing", str(caught.exception))

    def test_missing_end_marker(self):
        with self.assertRaises(SpanError) as caught:
            _splice_readme(f"HEAD\n{CROSSWALK_START}\nTAIL\n", ROWS)

        self.assertIn("CROSSWALK:END marker is missing", str(caught.exception))

    def test_duplicate_start_marker(self):
        document = (
            f"HEAD\n{CROSSWALK_START}\n{CROSSWALK_START}\n{CROSSWALK_END}\nTAIL\n"
        )

        with self.assertRaises(SpanError) as caught:
            _splice_readme(document, ROWS)

        self.assertIn("CROSSWALK:START marker is duplicated", str(caught.exception))

    def test_reversed_markers(self):
        document = f"HEAD\n{CROSSWALK_END}\n{CROSSWALK_START}\nTAIL\n"

        with self.assertRaises(SpanError) as caught:
            _splice_readme(document, ROWS)

        self.assertIn(
            "CROSSWALK:END appears before CROSSWALK:START",
            str(caught.exception),
        )

    def test_cr_marker_text(self):
        with self.assertRaises(SpanError) as caught:
            _splice_readme(host(STALE_BODY).replace("\n", "\r\n"), ROWS)

        self.assertIn("marked text contains CR", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
