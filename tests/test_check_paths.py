from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "build_crosswalk.py"
ARTIFACTS = (
    "mappings.yaml",
    "crosswalk.md",
    "crosswalk.json",
    "crosswalk.csv",
    "README.md",
)


class CheckPathTests(unittest.TestCase):
    def test_defaults_follow_source_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "src"
            source_dir.mkdir()
            for name in ARTIFACTS:
                shutil.copy(ROOT / name, source_dir / name)
            other = root / "other"
            other.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(source_dir / "mappings.yaml"),
                    "--check",
                ],
                cwd=other,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_paths_stay_relative_to_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "src"
            source_dir.mkdir()
            shutil.copy(ROOT / "mappings.yaml", source_dir / "mappings.yaml")
            for name in ("crosswalk.md", "crosswalk.json", "crosswalk.csv"):
                shutil.copy(ROOT / name, source_dir / name)
            cwd = root / "cwd"
            cwd.mkdir()
            for name in ("crosswalk.md", "crosswalk.json", "crosswalk.csv"):
                (cwd / name).write_text("stale\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(source_dir / "mappings.yaml"),
                    "--check",
                    "--out-md",
                    "crosswalk.md",
                    "--out-json",
                    "crosswalk.json",
                    "--out-csv",
                    "crosswalk.csv",
                ],
                cwd=cwd,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("drift", result.stderr)


if __name__ == "__main__":
    unittest.main()
