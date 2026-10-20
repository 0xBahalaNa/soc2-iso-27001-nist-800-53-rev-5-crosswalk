from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import build_crosswalk

FIXED_ROWS = [
    {
        "soc2_cc": "CC1.1",
        "nist_800_53": "AC-1",
        "iso_27001_2022": "A.5.1",
        "confidence": "Strong",
        "rationale": "Policy exists.",
    },
    {
        "soc2_cc": "CC1.1",
        "nist_800_53": "AC-2",
        "iso_27001_2022": "A.5.2",
        "confidence": "Partial",
        "rationale": "Only part of the account lifecycle.",
    },
]

MARKDOWN = """\
# SOC 2 / ISO 27001 / NIST 800-53 Rev 5 Crosswalk

Pivot: SOC 2 Trust Services Criteria (Common Criteria). NIST 800-53 Rev 5 is the bridge column; ISO 27001:2022 Annex A is the third column.

| SOC 2 CC | NIST 800-53 | ISO 27001:2022 | Confidence | Rationale |
| --- | --- | --- | --- | --- |
| CC1.1 | AC-1 | A.5.1 | Strong | Policy exists. |
| CC1.1 | AC-2 | A.5.2 | Partial | Only part of the account lifecycle. |

## Gaps & Conflicts

### CC1.1 / AC-2 (Partial)

Only part of the account lifecycle.

"""

JSON = """\
[
  {
    "soc2_cc": "CC1.1",
    "nist_800_53": "AC-1",
    "iso_27001_2022": "A.5.1",
    "confidence": "Strong",
    "rationale": "Policy exists."
  },
  {
    "soc2_cc": "CC1.1",
    "nist_800_53": "AC-2",
    "iso_27001_2022": "A.5.2",
    "confidence": "Partial",
    "rationale": "Only part of the account lifecycle."
  }
]
"""

CSV = """\
soc2_cc,nist_800_53,iso_27001_2022,confidence,rationale
CC1.1,AC-1,A.5.1,Strong,Policy exists.
CC1.1,AC-2,A.5.2,Partial,Only part of the account lifecycle.
"""


class RenderByteStabilityTests(unittest.TestCase):
    def test_render_markdown_bytes(self) -> None:
        actual = build_crosswalk.render_markdown(FIXED_ROWS).encode("utf-8")
        self.assertEqual(actual, MARKDOWN.encode("utf-8"))

    def test_render_json_bytes(self) -> None:
        actual = build_crosswalk.render_json(FIXED_ROWS).encode("utf-8")
        self.assertEqual(actual, JSON.encode("utf-8"))

    def test_render_csv_bytes(self) -> None:
        actual = build_crosswalk.render_csv(FIXED_ROWS).encode("utf-8")
        self.assertEqual(actual, CSV.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
