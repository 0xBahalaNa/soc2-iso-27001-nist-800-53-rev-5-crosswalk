![License](https://img.shields.io/badge/License-MIT-green?style=flat)
![SOC 2](https://img.shields.io/badge/SOC%202-Trust%20Services%20Criteria-2b6cb0?style=flat)
![ISO 27001](https://img.shields.io/badge/ISO%2FIEC-27001%3A2022-005387?style=flat)
![NIST 800-53](https://img.shields.io/badge/NIST-800--53%20Rev%205-004990?style=flat)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab?style=flat)

# Unified Controls Crosswalk

A crosswalk that pivots on **SOC 2 Trust Services Criteria (Common Criteria)** and maps **NIST 800-53 Rev 5** and **ISO 27001:2022 Annex A** onto each criterion — every row carrying a confidence label (Strong / Partial / Contextual) and a short "why this mapping" rationale. The mapping data lives in a single `mappings.yaml`; a small Python build script emits Markdown, JSON, and CSV, with a `--check` validate-only gate so the artifacts never drift from the source.

> **Status:** v1.0 in active development. The crosswalk table is generated from `mappings.yaml` once the build script lands; until then the families in scope are listed below.

## Why This Exists

A security program that answers to more than one framework ends up maintaining the same control intent in three different places — one spreadsheet for SOC 2, one for ISO 27001, one for NIST. This crosswalk collapses that into a single source of truth. It pivots on SOC 2 Common Criteria — the auditor-language most commercial programs already speak — maps the NIST 800-53 Rev 5 and ISO 27001:2022 Annex A equivalents onto each criterion, and is explicit about where a mapping is clean versus where the frameworks genuinely diverge.

I built it to **learn cross-framework control mapping by doing it** — reading the source standards, deciding each equivalence myself, and writing down the reasoning rather than copying a vendor's mapping table.

## Why SOC 2 as the Pivot

NIST 800-53 has the most granular catalog (1000+ controls), but it's engineer-language. SOC 2 Common Criteria (~33 CC) is the auditor-language commercial programs already understand. Pivoting on SOC 2 keeps the crosswalk compact and readable while preserving engineering precision through the NIST column. NIST 800-53 stays the bridge — every SOC 2 row maps to one or more NIST controls; the reverse isn't true.

## Scope (v1.0)

- **Frameworks:** SOC 2 TSC (pivot), NIST 800-53 Rev 5, ISO 27001:2022 Annex A
- **Control families:** Access Control (AC), Identification & Authentication (IA), Audit & Accountability (AU), Configuration Management (CM)
- **Planned (v1.1+):** CIS Controls v8 IG3 column, NIST CSF 2.0 overlay
- **Out of scope:** OT/ICS-specific frameworks (e.g., NERC CIP) — a separate concern, not a crosswalk row

## Controls Addressed

Generated from `mappings.yaml` via `build_crosswalk.py`. v1.0 anchors, by NIST family:

| NIST 800-53 Rev 5 | Family | SOC 2 neighborhood |
|---|---|---|
| AC-2, AC-3, AC-6 | Access Control | CC6 — logical access |
| IA-2, IA-5 | Identification & Authentication | CC6 — authentication |
| AU-2, AU-6 | Audit & Accountability | CC7 — system operations / monitoring |
| CM-2, CM-6 | Configuration Management | CC8 — change management |

*The full SOC 2 ↔ NIST ↔ ISO rows, confidence labels, and rationale are emitted from `mappings.yaml` in v1.0.*

## Gaps & Conflicts

Not every cross-framework mapping is one-to-one. Rows where the frameworks diverge in scope, depth, or framing are labeled **Partial** or **Contextual** and surfaced in a dedicated section. The point of the crosswalk is to be honest about where a single piece of evidence satisfies all three frameworks and where it doesn't — that's where multi-framework programs actually spend effort.

## How an Auditor Uses This Output

For a given SOC 2 Common Criterion, the row names the corresponding NIST 800-53 Rev 5 control(s) and ISO 27001:2022 Annex A control, the confidence in that equivalence, and the rationale. An auditor can reuse one piece of evidence across frameworks where the mapping is **Strong**, and knows to collect framework-specific evidence where it's **Partial** or **Contextual**. `crosswalk.csv` drops into a workpaper or GRC platform without manual transcription; `crosswalk.json` feeds an evidence pipeline.

## Automation & Compliance-as-Code

- **Single source of truth:** mappings live in version-controlled YAML, not a spreadsheet — diffable and reviewable in pull requests.
- **Machine-readable outputs:** the build emits JSON and CSV alongside the Markdown table, so the crosswalk feeds tooling, not just human eyes.
- **Validate-only gate:** `build_crosswalk.py --check` parses and validates the source without emitting (non-zero exit on failure) — drop it into CI to keep the emitted artifacts in sync with `mappings.yaml`.

## Sample Output

*The shape `build_crosswalk.py` emits from `mappings.yaml` (illustrative; finalized in v1.0):*

`crosswalk.csv`
```csv
soc2_cc,nist_800_53,iso_27001_2022,confidence,rationale
CC6.1,AC-3,A.5.15,Strong,"Access enforcement at the policy/system layer."
CC8.1,CM-2,A.8.9,Partial,"SOC 2 frames change mgmt broadly; NIST CM-2 is baseline-config specific."
```

`crosswalk.json`
```json
{
  "soc2_cc": "CC6.1",
  "nist_800_53": "AC-3",
  "iso_27001_2022": "A.5.15",
  "confidence": "Strong",
  "rationale": "All address access enforcement at the policy/system layer; SOC 2 frames it as logical access, NIST as the enforcement mechanism, ISO as policy."
}
```

## Quickstart

*Target interface (build lands in v1.0):*

```bash
git clone https://github.com/0xBahalaNa/soc2-iso27001-nist-crosswalk.git
cd soc2-iso27001-nist-crosswalk
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Build all artifacts from the YAML source
python build_crosswalk.py --source mappings.yaml \
  --out-md crosswalk.md --out-json crosswalk.json --out-csv crosswalk.csv

# CI validate-only mode (no emit; non-zero exit on validation failure)
python build_crosswalk.py --source mappings.yaml --check
```

## Forward Path (v1.1+)

- Add a CIS Controls v8 IG3 column
- Add a NIST CSF 2.0 overlay (Functions / Categories / Subcategories)
- Expand to additional families (System & Information Integrity, Incident Response)

## License

MIT
