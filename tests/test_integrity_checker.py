from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from integrity_checker import compare, load_baseline, main, scan


class IntegrityCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.root = self.parent / "files"
        self.root.mkdir()
        self.baseline = self.parent / "baseline.json"
        (self.root / "sample.txt").write_bytes(b"original\n")

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            result = main(list(arguments))
        return result, output.getvalue(), errors.getvalue()

    def create_baseline(self) -> None:
        result, _, errors = self.run_cli(
            "baseline", "--directory", str(self.root),
            "--output", str(self.baseline),
        )
        self.assertEqual((result, errors), (0, ""))

    def check(self) -> tuple[int, str, str]:
        return self.run_cli(
            "check", "--directory", str(self.root),
            "--baseline", str(self.baseline),
        )

    def test_known_sha256_and_git_exclusion(self) -> None:
        git = self.root / ".git"
        git.mkdir()
        (git / "config").write_text("not scanned", encoding="utf-8")
        self.assertEqual(
            scan(self.root),
            {"sample.txt": hashlib.sha256(b"original\n").hexdigest()},
        )

    def test_unchanged_files(self) -> None:
        self.create_baseline()
        result, output, errors = self.check()
        self.assertEqual(result, 0)
        self.assertIn("OK: 1 file(s)", output)
        self.assertEqual(errors, "")

    def test_all_change_categories(self) -> None:
        (self.root / "removed.txt").write_text("old", encoding="utf-8")
        self.create_baseline()
        (self.root / "removed.txt").unlink()
        (self.root / "sample.txt").write_text("modified", encoding="utf-8")
        (self.root / "added.txt").write_text("new", encoding="utf-8")
        result, output, errors = self.check()
        self.assertEqual(result, 1)
        self.assertEqual(
            output,
            "ADDED: added.txt\nCHANGED: sample.txt\nMISSING: removed.txt\n",
        )
        self.assertEqual(errors, "")

    def test_baseline_inside_root_is_rejected(self) -> None:
        result, _, errors = self.run_cli(
            "baseline", "--directory", str(self.root),
            "--output", str(self.root / "baseline.json"),
        )
        self.assertEqual(result, 2)
        self.assertIn("outside", errors)
        self.assertFalse((self.root / "baseline.json").exists())

    def test_missing_directory_is_an_error(self) -> None:
        result, _, errors = self.run_cli(
            "baseline", "--directory", str(self.parent / "absent"),
            "--output", str(self.baseline),
        )
        self.assertEqual(result, 2)
        self.assertTrue(errors.startswith("Error:"))

    def test_missing_baseline_is_an_error(self) -> None:
        result, _, errors = self.check()
        self.assertEqual(result, 2)
        self.assertTrue(errors.startswith("Error:"))

    def test_invalid_json_is_an_error(self) -> None:
        self.baseline.write_text("{", encoding="utf-8")
        result, _, errors = self.check()
        self.assertEqual(result, 2)
        self.assertTrue(errors.startswith("Error:"))

    def test_invalid_baseline_schema_and_entries(self) -> None:
        invalid = [
            [], {"version": True, "files": {}}, {"version": 2, "files": {}},
            {"version": 1, "files": []},
            *[
                {"version": 1, "files": {name: digest}}
                for name, digest in [
                    ("../outside", "a" * 64), ("/absolute", "a" * 64),
                    ("C:\\file", "a" * 64), ("a/./b", "a" * 64),
                    ("sample.txt", 123), ("sample.txt", "x" * 64),
                ]
            ],
        ]
        for data in invalid:
            with self.subTest(data=data):
                self.baseline.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_baseline(self.baseline)

    def test_nested_files_use_portable_paths(self) -> None:
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "empty.bin").write_bytes(b"")
        self.assertEqual(scan(self.root)["nested/empty.bin"],
                         hashlib.sha256(b"").hexdigest())

    def test_empty_directory(self) -> None:
        (self.root / "sample.txt").unlink()
        self.create_baseline()
        self.assertEqual(self.check()[0], 0)

    def test_compare_is_sorted(self) -> None:
        self.assertEqual(compare({}, {"z": "1", "a": "2"})["added"], ["a", "z"])

    def test_failed_save_reports_error(self) -> None:
        result, _, errors = self.run_cli(
            "baseline", "--directory", str(self.root),
            "--output", str(self.parent / "absent" / "baseline.json"),
        )
        self.assertEqual(result, 2)
        self.assertTrue(errors.startswith("Error:"))


if __name__ == "__main__":
    unittest.main()
