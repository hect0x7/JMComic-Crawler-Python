"""Build GitHub Release metadata from a release commit and changelog."""

import ast
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = Path("src/jmcomic/__init__.py")
CHANGELOG_FILE = Path("CHANGELOG.md")
RELEASE_BODY_FILE = Path("release_body.txt")
RELEASE_SUBJECT_PATTERN = re.compile(r"^v(?P<version>\d+\.\d+\.\d+):(?:\s.*)?$")
VERSION_HEADING_PATTERN = re.compile(
    r"^## \[(?P<version>[^]]+)] - (?P<date>\d{4}-\d{2}-\d{2})\s*$",
    re.MULTILINE,
)


def read_source_version(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "__version__":
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    raise ValueError(f"Static __version__ assignment not found in {path}")


def read_release_version(commit_message: str) -> str:
    subject = commit_message.splitlines()[0].strip() if commit_message else ""
    match = RELEASE_SUBJECT_PATTERN.fullmatch(subject)
    if match is None:
        raise ValueError(f"Release commit must match v{{version}}: summary, got: {subject}")
    return match.group("version")


def extract_release_body(changelog: str, version: str) -> str:
    matches = [match for match in VERSION_HEADING_PATTERN.finditer(changelog) if match.group("version") == version]
    if not matches:
        raise ValueError(f"Changelog section not found: ## [{version}] - YYYY-MM-DD")
    if len(matches) > 1:
        raise ValueError(f"Duplicate changelog sections found for version {version}")

    match = matches[0]
    next_heading = re.search(r"^## \[", changelog[match.end():], re.MULTILINE)
    section_end = match.end() + next_heading.start() if next_heading else len(changelog)
    body = changelog[match.end():section_end].strip()
    if not body:
        raise ValueError(f"Changelog section for version {version} is empty")
    return body


def count_release_entries(body: str) -> int:
    return sum(1 for line in body.splitlines() if line.lstrip().startswith("- "))


def build_release_metadata(
        commit_message: Optional[str] = None,
        root_dir: Optional[Path] = None,
) -> Tuple[str, str]:
    root_dir = root_dir or ROOT_DIR
    source_version = read_source_version(root_dir / VERSION_FILE)
    if commit_message is not None:
        release_version = read_release_version(commit_message)
        if release_version != source_version:
            raise ValueError(
                f"Version mismatch: release commit={release_version}, __init__.py={source_version}"
            )

    changelog = (root_dir / CHANGELOG_FILE).read_text(encoding="utf-8")
    return f"v{source_version}", extract_release_body(changelog, source_version)


def add_output(key: str, value: str, output_path: Optional[str] = None) -> None:
    output_path = output_path or os.environ.get("GITHUB_OUTPUT")
    if output_path is None:
        print(f"{key}={value}")
        return
    with Path(output_path).open("a", encoding="utf-8") as output_file:
        output_file.write(f"{key}={value}\n")


def main(commit_message: Optional[str] = None) -> int:
    try:
        tag, body = build_release_metadata(commit_message)
        (ROOT_DIR / RELEASE_BODY_FILE).write_text(f"{body}\n", encoding="utf-8")
        add_output("tag", tag)
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"Release metadata error: {exc}", file=sys.stderr)
        return 1

    print(f"Release version: {tag.removeprefix('v')}")
    print(f"Changelog entries: {count_release_entries(body)}")
    print(f"Release body source: {CHANGELOG_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) >= 2 else None))
