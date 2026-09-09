"""Tests for changelog-driven GitHub Release metadata."""

import importlib.util
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from test_jmcomic import *


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RELEASE_SCRIPT = PROJECT_ROOT / ".github" / "release.py"
SPEC = importlib.util.spec_from_file_location("jmcomic_release", RELEASE_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load release script: {RELEASE_SCRIPT}")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class Test_Release(unittest.TestCase):

    def create_project(self, root: Path, version: str, changelog: str) -> None:
        package_dir = root / "src" / "jmcomic"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text(f"__version__ = '{version}'\n", encoding="utf-8")
        (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")

    def test_release_body_comes_from_matching_changelog_section(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_project(
                root,
                "2.7.4",
                """# Changelog

## [2.7.4] - 2026-08-08

### Added
- Manifest release notes.

## [2.7.3] - 2026-07-01

### Fixed
- Previous release.
""",
            )

            tag, body = release.build_release_metadata("v2.7.4: text ignored by release body", root)

            self.assertEqual(tag, "v2.7.4")
            self.assertEqual(body, "### Added\n- Manifest release notes.")

    def test_rejects_commit_and_source_version_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_project(
                root,
                "2.7.4",
                "## [2.7.4] - 2026-08-08\n\n### Added\n- Entry.\n",
            )

            with self.assertRaisesRegex(ValueError, "Version mismatch"):
                release.build_release_metadata("v2.7.5: wrong version", root)

    def test_manual_release_uses_source_version_without_commit_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_project(
                root,
                "2.7.4",
                "## [2.7.4] - 2026-08-08\n\n### Fixed\n- Manual recovery.\n",
            )

            tag, body = release.build_release_metadata(root_dir=root)

            self.assertEqual(tag, "v2.7.4")
            self.assertEqual(body, "### Fixed\n- Manual recovery.")

    def test_rejects_missing_duplicate_or_empty_changelog_section(self):
        cases = (
            "## [2.7.3] - 2026-08-01\n\n### Fixed\n- Old.\n",
            "## [2.7.4] - 2026-08-08\n- First.\n\n## [2.7.4] - 2026-08-07\n- Duplicate.\n",
            "## [2.7.4] - 2026-08-08\n\n## [2.7.3] - 2026-08-01\n- Old.\n",
        )
        for changelog in cases:
            with self.subTest(changelog=changelog), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                self.create_project(root, "2.7.4", changelog)
                with self.assertRaises(ValueError):
                    release.build_release_metadata("v2.7.4: release", root)

    def test_main_writes_changelog_body_and_tag_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_path = root / "github-output.txt"
            self.create_project(
                root,
                "2.7.4",
                "## [2.7.4] - 2026-08-08\n\n### Fixed\n- Reliable release notes.\n",
            )

            with patch.object(release, "ROOT_DIR", root), patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
                self.assertEqual(release.main("v2.7.4: commit summary only"), 0)

            self.assertEqual(
                (root / "release_body.txt").read_text(encoding="utf-8"),
                "### Fixed\n- Reliable release notes.\n",
            )
            self.assertEqual(output_path.read_text(encoding="utf-8"), "tag=v2.7.4\n")

    def test_release_entry_count_uses_changelog_bullets(self):
        body = "### Added\n- First.\n- Second.\n\n### Fixed\n- Third."

        self.assertEqual(release.count_release_entries(body), 3)

    def test_python_39_remains_install_compatible(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        setup_py = (PROJECT_ROOT / "setup.py").read_text(encoding="utf-8")

        self.assertIn('requires-python = ">=3.9"', pyproject)
        self.assertIn('python_requires=">=3.9"', setup_py)
        self.assertIn("Programming Language :: Python :: 3.9", pyproject)
        self.assertIn("Programming Language :: Python :: 3.9", setup_py)


if __name__ == "__main__":
    unittest.main()
