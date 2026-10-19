#!/usr/bin/env python3
"""Build crosswalk artifacts from mappings.yaml."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

DEFAULT_OUT_MD = Path("crosswalk.md")
DEFAULT_OUT_JSON = Path("crosswalk.json")
DEFAULT_OUT_CSV = Path("crosswalk.csv")

VALID_CONFIDENCE = frozenset({"Strong", "Partial", "Contextual"})
SOC2_CC_PATTERN = re.compile(r"^CC(\d+)\.(\d+)\Z")
NIST_PATTERN = re.compile(r"^([A-Z]{2})-(\d+)(?:\((\d+)\))?\Z")
ISO_PATTERN = re.compile(r"^A\.([5-8])\.(\d+)\Z")
FIELDNAMES = [
    "soc2_cc",
    "nist_800_53",
    "iso_27001_2022",
    "confidence",
    "rationale",
]
TOP_LEVEL_KEYS = frozenset({"metadata", "mappings"})
METADATA_STRING_FIELDS = (
    "version",
    "pivot_framework",
    "bridge_framework",
    "third_framework",
)
METADATA_KEYS = frozenset(METADATA_STRING_FIELDS + ("row_count",))
_GAP_LEADER = re.compile(r"^([#>\-|])", re.MULTILINE)


def load_mappings(path: Path) -> dict[str, Any]:
    """Read and parse mappings.yaml with yaml.safe_load."""
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        raise ValueError(f"{path}: file is empty")
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be a mapping")
    return data


def _metadata_errors(metadata: Any, mappings: Any) -> list[str]:
    if not isinstance(metadata, dict):
        return ["metadata must be a mapping"]

    errors: list[str] = []
    for key in sorted(metadata):
        if key not in METADATA_KEYS:
            errors.append(f"metadata: unknown field {key!r}")

    for key in METADATA_STRING_FIELDS:
        if key not in metadata:
            errors.append(f"metadata: missing required field '{key}'")
            continue
        value = metadata[key]
        if not isinstance(value, str) or not value.strip():
            errors.append(
                f"metadata: {key} must be a non-empty string (got {value!r})"
            )

    if "row_count" not in metadata:
        errors.append("metadata: missing required field 'row_count'")
    else:
        count = metadata["row_count"]
        if type(count) is not int:
            errors.append(f"metadata: row_count must be an int (got {count!r})")
        elif isinstance(mappings, list) and count != len(mappings):
            errors.append(
                f"metadata: row_count must equal {len(mappings)} (got {count})"
            )
    return errors


def _control_list_errors(
    prefix: str,
    field: str,
    value: Any,
    pattern: re.Pattern[str],
) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{prefix}: {field} must be a non-empty list"]

    errors: list[str] = []
    seen: list[Any] = []
    for control in value:
        if control in seen:
            errors.append(f"{prefix}: duplicate {field} control {control!r}")
        else:
            seen.append(control)
        if not isinstance(control, str) or pattern.match(control) is None:
            errors.append(f"{prefix}: invalid {field} control {control!r}")
    return errors


def validate_mappings(data: dict[str, Any]) -> list[str]:
    """Return a list of validation error messages (empty if valid)."""
    errors: list[str] = []

    for key in sorted(data):
        if key not in TOP_LEVEL_KEYS:
            errors.append(f"unknown top-level key {key!r}")

    if "metadata" not in data:
        errors.append("missing required top-level key 'metadata'")
    else:
        errors.extend(_metadata_errors(data["metadata"], data.get("mappings")))

    mappings = data.get("mappings")
    if not isinstance(mappings, list):
        errors.append("mappings must be a list")
        return errors

    if len(mappings) < 1:
        errors.append(f"mappings must contain at least 1 row (found {len(mappings)})")

    seen_rows: list[tuple[int, dict[str, Any]]] = []
    for index, row in enumerate(mappings, start=1):
        prefix = f"row {index}"

        if not isinstance(row, dict):
            errors.append(f"{prefix}: must be a mapping")
            continue

        for earlier, previous in seen_rows:
            if previous == row:
                errors.append(f"{prefix}: duplicate of row {earlier}")
                break
        seen_rows.append((index, row))

        for key in sorted(row):
            if key not in FIELDNAMES:
                errors.append(f"{prefix}: unknown field {key!r}")

        for field in FIELDNAMES:
            if field not in row:
                errors.append(f"{prefix}: missing required field '{field}'")

        soc2_cc = row.get("soc2_cc")
        if not isinstance(soc2_cc, str) or SOC2_CC_PATTERN.match(soc2_cc) is None:
            errors.append(f"{prefix}: soc2_cc must match CC#.# (got {soc2_cc!r})")

        errors.extend(
            _control_list_errors(
                prefix, "nist_800_53", row.get("nist_800_53"), NIST_PATTERN
            )
        )
        errors.extend(
            _control_list_errors(
                prefix, "iso_27001_2022", row.get("iso_27001_2022"), ISO_PATTERN
            )
        )

        confidence = row.get("confidence")
        if confidence not in VALID_CONFIDENCE:
            errors.append(
                f"{prefix}: confidence must be one of "
                f"{sorted(VALID_CONFIDENCE)} (got {confidence!r})"
            )

        rationale = row.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"{prefix}: rationale must be a non-empty string")

    return errors


def _join_controls(controls: list[str]) -> str:
    return " / ".join(controls)


def _md_cell(value: str) -> str:
    flat = value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    return flat.replace("\\", "\\\\").replace("|", "\\|")


def _escape_gap_prose(text: str) -> str:
    return _GAP_LEADER.sub(r"\\\1", text)


def _matched_groups(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    found = pattern.match(value)
    if found is None:
        raise ValueError(f"unvalidated {label} {value!r}")
    return found


def _sort_key(
    row: dict[str, Any],
) -> tuple[
    tuple[int, int],
    tuple[tuple[str, int, tuple[int, ...]], ...],
    tuple[tuple[int, int], ...],
    str,
    str,
]:
    soc2 = _matched_groups(SOC2_CC_PATTERN, row["soc2_cc"], "soc2_cc")
    nist_keys: list[tuple[str, int, tuple[int, ...]]] = []
    for control in row["nist_800_53"]:
        family, number, enhancement = _matched_groups(
            NIST_PATTERN, control, "nist_800_53"
        ).groups()
        enh = () if enhancement is None else (int(enhancement),)
        nist_keys.append((family, int(number), enh))
    iso_keys: list[tuple[int, int]] = []
    for control in row["iso_27001_2022"]:
        clause, number = _matched_groups(
            ISO_PATTERN, control, "iso_27001_2022"
        ).groups()
        iso_keys.append((int(clause), int(number)))
    return (
        (int(soc2.group(1)), int(soc2.group(2))),
        tuple(nist_keys),
        tuple(iso_keys),
        row["confidence"],
        row["rationale"],
    )


def normalize_rows(mappings: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Sort rows deterministically and flatten control lists to display strings."""
    sorted_rows = sorted(mappings, key=_sort_key)
    normalized: list[dict[str, str]] = []

    for row in sorted_rows:
        normalized.append(
            {
                "soc2_cc": row["soc2_cc"],
                "nist_800_53": _join_controls(row["nist_800_53"]),
                "iso_27001_2022": _join_controls(row["iso_27001_2022"]),
                "confidence": row["confidence"],
                "rationale": " ".join(row["rationale"].split()),
            }
        )

    return normalized


def render_markdown(rows: list[dict[str, str]]) -> str:
    """Return a human-readable Markdown table plus Gaps & Conflicts section."""
    lines = [
        "# SOC 2 / ISO 27001 / NIST 800-53 Rev 5 Crosswalk",
        "",
        "Pivot: SOC 2 Trust Services Criteria (Common Criteria). "
        "NIST 800-53 Rev 5 is the bridge column; "
        "ISO 27001:2022 Annex A is the third column.",
        "",
        "| SOC 2 CC | NIST 800-53 | ISO 27001:2022 | Confidence | Rationale |",
        "| --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        lines.append(
            f"| {_md_cell(row['soc2_cc'])} | {_md_cell(row['nist_800_53'])} | "
            f"{_md_cell(row['iso_27001_2022'])} | {_md_cell(row['confidence'])} | "
            f"{_md_cell(row['rationale'])} |"
        )

    gap_rows = [row for row in rows if row["confidence"] != "Strong"]
    lines.extend(["", "## Gaps & Conflicts", ""])
    for row in gap_rows:
        lines.extend(
            [
                f"### {row['soc2_cc']} / {row['nist_800_53']} / "
                f"{row['iso_27001_2022']} ({row['confidence']})",
                "",
                _escape_gap_prose(row["rationale"]),
                "",
            ]
        )

    return "\n".join(lines) + "\n"


def render_json(rows: list[dict[str, str]]) -> str:
    """Return normalized rows as a JSON array string."""
    return json.dumps(rows, indent=2) + "\n"


def render_csv(rows: list[dict[str, str]]) -> str:
    """Return normalized rows as CSV with README field names."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _restore_outputs(
    temps: list[Path],
    published: list[tuple[Path, bytes | None]],
) -> OSError | None:
    restore_error: OSError | None = None
    for dest, prior in reversed(published):
        try:
            if prior is None:
                dest.unlink(missing_ok=True)
            else:
                dest.write_bytes(prior)
        except OSError as exc:
            restore_error = exc
    for tmp in temps:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError as exc:
            restore_error = exc
    return restore_error


def _commit_rendered(files: tuple[tuple[Path, str], ...]) -> None:
    temps: list[Path] = []
    published: list[tuple[Path, bytes | None]] = []
    try:
        staged: list[tuple[Path, Path]] = []
        for index, (dest, text) in enumerate(files):
            tmp = dest.with_name(f".{dest.name}.{os.getpid()}.{index}.tmp")
            tmp.write_text(text, encoding="utf-8", newline="")
            temps.append(tmp)
            staged.append((tmp, dest))
        priors: list[bytes | None] = []
        for _tmp, dest in staged:
            priors.append(dest.read_bytes() if dest.is_file() else None)
        for (tmp, dest), prior in zip(staged, priors):
            os.replace(tmp, dest)
            published.append((dest, prior))
    except OSError as original:
        restore_error = _restore_outputs(temps, published)
        if restore_error is not None:
            raise restore_error from original
        raise


def check_drift(
    rows: list[dict[str, str]],
    md_path: Path,
    json_path: Path,
    csv_path: Path,
    *,
    source_label: str = "mappings.yaml",
) -> list[str]:
    """Compare freshly rendered artifacts to on-disk files; return drift messages."""
    artifacts = (
        (md_path, render_markdown(rows)),
        (json_path, render_json(rows)),
        (csv_path, render_csv(rows)),
    )
    messages: list[str] = []

    for path, expected in artifacts:
        try:
            actual = path.read_bytes()
        except OSError as exc:
            messages.append(
                f"error: {path}: {exc} (expected from {source_label})"
            )
            continue

        if actual == expected.encode("utf-8"):
            continue

        messages.append(
            f"error: {path}: drift vs {source_label} (rebuild required)"
        )

    return messages


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build crosswalk artifacts from mappings.yaml"
    )
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Path to mappings.yaml",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Validate mappings and verify committed artifacts match a fresh build "
            "(no emit)"
        ),
    )
    parser.add_argument("--out-md", type=Path, help="Output Markdown path")
    parser.add_argument("--out-json", type=Path, help="Output JSON path")
    parser.add_argument("--out-csv", type=Path, help="Output CSV path")
    args = parser.parse_args()

    try:
        data = load_mappings(args.source)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    errors = validate_mappings(data)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    if args.check:
        md_path = args.out_md or DEFAULT_OUT_MD
        json_path = args.out_json or DEFAULT_OUT_JSON
        csv_path = args.out_csv or DEFAULT_OUT_CSV
        rows = normalize_rows(data["mappings"])
        drift_messages = check_drift(
            rows,
            md_path,
            json_path,
            csv_path,
            source_label=str(args.source),
        )
        if drift_messages:
            for message in drift_messages:
                print(message, file=sys.stderr)
            return 1
        return 0

    missing_outputs = [
        name
        for name, value in (
            ("--out-md", args.out_md),
            ("--out-json", args.out_json),
            ("--out-csv", args.out_csv),
        )
        if value is None
    ]
    if missing_outputs:
        parser.error(
            "the following arguments are required when not using --check: "
            + ", ".join(missing_outputs)
        )
    rows = normalize_rows(data["mappings"])
    rendered = (
        (args.out_md, render_markdown(rows)),
        (args.out_json, render_json(rows)),
        (args.out_csv, render_csv(rows)),
    )
    try:
        _commit_rendered(rendered)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
