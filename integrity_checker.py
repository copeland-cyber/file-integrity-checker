"""Create and compare SHA-256 baselines for local files."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile


def scan(directory: Path) -> dict[str, str]:
    root = directory.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    hashes: dict[str, str] = {}

    def walk_error(error: OSError) -> None:
        raise error

    for current, directories, files in os.walk(root, onerror=walk_error):
        directories[:] = sorted(
            name for name in directories
            if name != ".git" and not (Path(current) / name).is_symlink()
        )
        for name in sorted(files):
            path = Path(current) / name
            if path.is_symlink():
                continue
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            hashes[path.relative_to(root).as_posix()] = digest.hexdigest()
    return dict(sorted(hashes.items()))


def validate_baseline_location(directory: Path, baseline: Path) -> None:
    if baseline.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Store the baseline outside the scanned directory.")


def save_baseline(path: Path, hashes: dict[str, str]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as destination:
            temporary = Path(destination.name)
            json.dump({"version": 1, "files": hashes}, destination, indent=2)
            destination.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def load_baseline(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as source:
        data = json.load(source)
    if (
        not isinstance(data, dict)
        or type(data.get("version")) is not int
        or data["version"] != 1
        or not isinstance(data.get("files"), dict)
    ):
        raise ValueError("Invalid baseline: expected version 1 and a files object.")
    hashes: dict[str, str] = {}
    for name, digest in data["files"].items():
        relative = PurePosixPath(name)
        if (
            not name
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in name
            or ":" in name
            or relative.as_posix() != name
            or name == "."
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"Invalid baseline entry: {name!r}")
        hashes[name] = digest
    return hashes


def compare(
    expected: dict[str, str], actual: dict[str, str]
) -> dict[str, list[str]]:
    return {
        "added": sorted(actual.keys() - expected.keys()),
        "changed": sorted(
            name for name in expected.keys() & actual.keys()
            if expected[name] != actual[name]
        ),
        "missing": sorted(expected.keys() - actual.keys()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("baseline", help="Record current file hashes")
    create.add_argument("--directory", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("check", help="Compare against a saved baseline")
    check.add_argument("--directory", type=Path, required=True)
    check.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        baseline = args.output if args.command == "baseline" else args.baseline
        validate_baseline_location(args.directory, baseline)
        if args.command == "baseline":
            hashes = scan(args.directory)
            save_baseline(baseline, hashes)
            print(f"Baseline saved: {len(hashes)} file(s).")
            return 0
        expected = load_baseline(baseline)
        changes = compare(expected, scan(args.directory))
        for status, names in changes.items():
            for name in names:
                print(f"{status.upper()}: {name}")
        if any(changes.values()):
            return 1
        print(f"OK: {len(expected)} file(s) match the baseline.")
        return 0
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
