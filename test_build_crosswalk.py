from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import build_crosswalk as cw

ROOT = Path(__file__).resolve().parent


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "soc2_cc": "CC6.1",
        "nist_800_53": ["AC-3"],
        "iso_27001_2022": ["A.5.15"],
        "confidence": "Strong",
        "rationale": "The control covers the same access decision.",
    }
    row.update(overrides)
    return row


def _doc(rows: list[dict[str, object]], **metadata: object) -> dict[str, object]:
    block: dict[str, object] = {
        "version": "1.0",
        "pivot_framework": "SOC 2 TSC Common Criteria",
        "bridge_framework": "NIST 800-53 Rev 5",
        "third_framework": "ISO 27001:2022 Annex A",
        "row_count": len(rows),
    }
    block.update(metadata)
    return {"metadata": block, "mappings": rows}


class ValidationTests(unittest.TestCase):
    def test_shipped_mappings_are_valid(self) -> None:
        data = cw.load_mappings(ROOT / "mappings.yaml")
        self.assertEqual(cw.validate_mappings(data), [])

    def test_empty_file_names_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mappings.yaml"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                cw.load_mappings(path)
        self.assertIn(str(path), str(caught.exception))
        self.assertIn("empty", str(caught.exception))

    def test_malformed_yaml_fails_the_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mappings.yaml"
            path.write_text("mappings: [\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "build_crosswalk.py"), "--source", str(path), "--check"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_zero_rows_is_rejected(self) -> None:
        errors = cw.validate_mappings(_doc([]))
        self.assertIn("mappings must contain at least 1 row (found 0)", errors)

    def test_one_row_is_valid_and_renders(self) -> None:
        data = _doc([_row()])
        self.assertEqual(cw.validate_mappings(data), [])
        rendered = cw.render_markdown(cw.normalize_rows(data["mappings"]))
        self.assertIn("| CC6.1 | AC-3 | A.5.15 | Strong |", rendered)
        self.assertNotIn("### CC6.1", rendered)

    def test_missing_field_is_an_error_not_a_crash(self) -> None:
        row = _row()
        del row["soc2_cc"]
        errors = cw.validate_mappings(_doc([row]))
        self.assertIn("row 1: missing required field 'soc2_cc'", errors)

    def test_duplicate_rows_are_rejected(self) -> None:
        row = _row()
        errors = cw.validate_mappings(_doc([row, dict(row)]))
        self.assertIn("row 2: duplicate of row 1", errors)

    def test_same_soc2_with_different_controls_is_kept(self) -> None:
        rows = [
            _row(nist_800_53=["IA-2"], iso_27001_2022=["A.8.5", "A.5.16"]),
            _row(
                nist_800_53=["IA-5"],
                iso_27001_2022=["A.5.17"],
                confidence="Partial",
                rationale="ISO splits authenticator management from the mechanism.",
            ),
        ]
        self.assertEqual(cw.validate_mappings(_doc(rows)), [])

    def test_duplicate_controls_inside_a_list_are_rejected(self) -> None:
        errors = cw.validate_mappings(
            _doc(
                [
                    _row(
                        nist_800_53=["AC-3", "AC-3"],
                        iso_27001_2022=["A.5.15", "A.5.15"],
                    )
                ]
            )
        )
        self.assertIn("row 1: duplicate nist_800_53 control 'AC-3'", errors)
        self.assertIn("row 1: duplicate iso_27001_2022 control 'A.5.15'", errors)

    def test_unknown_row_field_and_top_level_key_are_rejected(self) -> None:
        row = _row(notes="typo")
        document = _doc([row])
        document["owner"] = "someone"
        errors = cw.validate_mappings(document)
        self.assertIn("unknown top-level key 'owner'", errors)
        self.assertIn("row 1: unknown field 'notes'", errors)

    def test_metadata_shape_is_checked(self) -> None:
        missing = {"mappings": [_row()]}
        self.assertIn(
            "missing required top-level key 'metadata'",
            cw.validate_mappings(missing),
        )

        not_a_mapping = _doc([_row()])
        not_a_mapping["metadata"] = ["version"]
        self.assertIn("metadata must be a mapping", cw.validate_mappings(not_a_mapping))

        unknown = _doc([_row()], owner="nope")
        self.assertIn("metadata: unknown field 'owner'", cw.validate_mappings(unknown))

        bad_count = _doc([_row()], row_count=2)
        self.assertIn("metadata: row_count must equal 1 (got 2)", cw.validate_mappings(bad_count))

        flagged = _doc([_row()], row_count=True)
        self.assertIn(
            "metadata: row_count must be an int (got True)",
            cw.validate_mappings(flagged),
        )

        blank = _doc([_row()], version="  ")
        self.assertIn(
            "metadata: version must be a non-empty string (got '  ')",
            cw.validate_mappings(blank),
        )

    def test_trailing_newline_ids_are_rejected(self) -> None:
        errors = cw.validate_mappings(
            _doc(
                [
                    _row(
                        soc2_cc="CC6.1\n",
                        nist_800_53=["AC-3\n"],
                        iso_27001_2022=["A.5.15\n"],
                    )
                ]
            )
        )
        self.assertTrue(any("soc2_cc" in error for error in errors))
        self.assertIn("row 1: invalid nist_800_53 control 'AC-3\\n'", errors)
        self.assertIn("row 1: invalid iso_27001_2022 control 'A.5.15\\n'", errors)
        self.assertEqual(cw.validate_mappings(_doc([_row(nist_800_53=["AC-2(1)"])])), [])


class SortAndMarkdownTests(unittest.TestCase):
    def test_multi_digit_ids_sort_numerically_and_the_key_is_total(self) -> None:
        rows = [
            _row(soc2_cc="CC10.1", nist_800_53=["AC-2", "AC-6"], iso_27001_2022=["A.8.10"]),
            _row(soc2_cc="CC2.1", nist_800_53=["AC-10"], iso_27001_2022=["A.5.15"]),
            _row(soc2_cc="CC2.1", nist_800_53=["AC-2", "AC-3"], iso_27001_2022=["A.5.9"]),
            _row(soc2_cc="CC2.1", nist_800_53=["AC-2(1)"], iso_27001_2022=["A.5.16"]),
            _row(soc2_cc="CC2.1", nist_800_53=["AC-2"], iso_27001_2022=["A.8.3"]),
        ]
        ordered = cw.normalize_rows(rows)
        self.assertEqual(
            [(row["soc2_cc"], row["nist_800_53"]) for row in ordered],
            [
                ("CC2.1", "AC-2"),
                ("CC2.1", "AC-2 / AC-3"),
                ("CC2.1", "AC-2(1)"),
                ("CC2.1", "AC-10"),
                ("CC10.1", "AC-2 / AC-6"),
            ],
        )

    def test_iso_ids_sort_numerically_when_soc2_and_nist_tie(self) -> None:
        rows = [
            _row(iso_27001_2022=["A.8.10"]),
            _row(iso_27001_2022=["A.8.3"]),
            _row(iso_27001_2022=["A.5.15"]),
        ]
        ordered = cw.normalize_rows(rows)
        self.assertEqual(
            [row["iso_27001_2022"] for row in ordered],
            ["A.5.15", "A.8.3", "A.8.10"],
        )

    def test_confidence_and_rationale_break_remaining_ties(self) -> None:
        rows = [
            _row(confidence="Strong", rationale="zeta"),
            _row(confidence="Contextual", rationale="zeta"),
            _row(confidence="Strong", rationale="alpha"),
        ]
        ordered = cw.normalize_rows(rows)
        self.assertEqual(
            [(row["confidence"], row["rationale"]) for row in ordered],
            [("Contextual", "zeta"), ("Strong", "alpha"), ("Strong", "zeta")],
        )

    def test_shipped_rows_keep_their_json_order(self) -> None:
        data = cw.load_mappings(ROOT / "mappings.yaml")
        rows = cw.normalize_rows(data["mappings"])
        committed = json.loads((ROOT / "crosswalk.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, committed)

    def test_gap_heading_includes_iso_and_escapes_leading_markup(self) -> None:
        rows = [
            {
                "soc2_cc": "CC8.1",
                "nist_800_53": "CM-6",
                "iso_27001_2022": "A.8.9",
                "confidence": "Partial",
                "rationale": "- ticket\n# later\n> note\n| cell\nstill | fine",
            },
            {
                "soc2_cc": "CC8.1",
                "nist_800_53": "CM-6",
                "iso_27001_2022": "A.8.32",
                "confidence": "Contextual",
                "rationale": "CM-6 is settings state.",
            },
        ]
        rendered = cw.render_markdown(rows)
        self.assertIn("### CC8.1 / CM-6 / A.8.9 (Partial)", rendered)
        self.assertIn("### CC8.1 / CM-6 / A.8.32 (Contextual)", rendered)
        self.assertNotIn("### CC8.1 / CM-6 (Partial)", rendered)
        self.assertIn("\\- ticket", rendered)
        self.assertIn("\\# later", rendered)
        self.assertIn("\\> note", rendered)
        self.assertIn("\\| cell", rendered)
        self.assertIn("still | fine", rendered)
        self.assertIn(
            "| CC8.1 | CM-6 | A.8.9 | Partial | - ticket # later > note \\| cell still \\| fine |",
            rendered,
        )

    def test_table_cell_escapes_backslash_before_pipe_and_flattens_newlines(self) -> None:
        def rationale_cell(rationale: str) -> str:
            rendered = cw.render_markdown(
                [
                    {
                        "soc2_cc": "CC6.1",
                        "nist_800_53": "AC-3",
                        "iso_27001_2022": "A.5.15",
                        "confidence": "Strong",
                        "rationale": rationale,
                    }
                ]
            )
            return next(line for line in rendered.splitlines() if line.startswith("| CC6.1 |"))

        self.assertIn("| a\\|b |", rationale_cell("a|b"))
        self.assertIn("| a\\\\\\|b |", rationale_cell("a\\|b"))
        self.assertIn("| a\\\\b |", rationale_cell("a\\b"))
        self.assertIn("| a b |", rationale_cell("a\nb"))
        self.assertIn("| a b |", rationale_cell("a\r\nb"))
        self.assertIn("| a b |", rationale_cell("a\rb"))


class EmitTests(unittest.TestCase):
    def test_commit_writes_all_three_and_a_repeat_matches(self) -> None:
        data = cw.load_mappings(ROOT / "mappings.yaml")
        rows = cw.normalize_rows(data["mappings"])
        texts = (
            cw.render_markdown(rows),
            cw.render_json(rows),
            cw.render_csv(rows),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = tuple(
                (root / name, text)
                for name, text in zip(("crosswalk.md", "crosswalk.json", "crosswalk.csv"), texts)
            )
            cw._commit_rendered(files)
            cw._commit_rendered(files)
            for path, text in files:
                self.assertEqual(path.read_bytes(), text.encode("utf-8"))
            self.assertEqual(list(root.glob(".*.tmp")), [])

    def test_failed_later_write_restores_the_earlier_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            markdown = root / "crosswalk.md"
            blocked = root / "crosswalk.json"
            csv_path = root / "crosswalk.csv"
            markdown.write_text("old-md\n", encoding="utf-8")
            csv_path.write_text("old-csv\n", encoding="utf-8")
            blocked.mkdir()
            with self.assertRaises(OSError):
                cw._commit_rendered(
                    (
                        (markdown, "new-md\n"),
                        (blocked, "new-json\n"),
                        (csv_path, "new-csv\n"),
                    )
                )
            self.assertEqual(markdown.read_text(encoding="utf-8"), "old-md\n")
            self.assertEqual(csv_path.read_text(encoding="utf-8"), "old-csv\n")
            self.assertTrue(blocked.is_dir())
            self.assertEqual(list(root.glob(".*.tmp")), [])

    def test_failed_temp_write_leaves_existing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            markdown = root / "crosswalk.md"
            markdown.write_text("stay\n", encoding="utf-8")
            missing = root / "missing" / "crosswalk.json"
            with self.assertRaises(OSError):
                cw._commit_rendered(
                    (
                        (markdown, "changed\n"),
                        (missing, "json\n"),
                    )
                )
            self.assertEqual(markdown.read_text(encoding="utf-8"), "stay\n")
            self.assertFalse(missing.exists())
            self.assertEqual(list(root.glob(".*.tmp")), [])

    def test_cli_missing_source_returns_1(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "build_crosswalk.py"),
                "--source",
                str(ROOT / "no-such.yaml"),
                "--check",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("error:", result.stderr)
        self.assertIn("no-such.yaml", result.stderr)

    def test_cli_failed_output_leaves_the_other_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            markdown = root / "crosswalk.md"
            blocked = root / "crosswalk.json"
            csv_path = root / "crosswalk.csv"
            markdown.write_text("old-md\n", encoding="utf-8")
            csv_path.write_text("old-csv\n", encoding="utf-8")
            blocked.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "build_crosswalk.py"),
                    "--source",
                    str(ROOT / "mappings.yaml"),
                    "--out-md",
                    str(markdown),
                    "--out-json",
                    str(blocked),
                    "--out-csv",
                    str(csv_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(markdown.read_text(encoding="utf-8"), "old-md\n")
            self.assertEqual(csv_path.read_text(encoding="utf-8"), "old-csv\n")
            self.assertTrue(blocked.is_dir())

    def test_cli_check_accepts_the_committed_artifacts(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "build_crosswalk.py"),
                "--source",
                str(ROOT / "mappings.yaml"),
                "--check",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
