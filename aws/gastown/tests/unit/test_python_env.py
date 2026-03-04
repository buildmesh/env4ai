"""Structural tests for the consolidated uv Python environment at aws/."""

import tomllib
import unittest
from pathlib import Path

AWS_ROOT = Path(__file__).parents[3]


class PythonEnvStructureTests(unittest.TestCase):
    def test_root_pyproject_exists(self) -> None:
        """Expected: single pyproject.toml lives at aws/ root."""
        self.assertTrue((AWS_ROOT / "pyproject.toml").exists())

    def test_root_pyproject_name(self) -> None:
        """Expected: root pyproject.toml project name is 'aws'."""
        with open(AWS_ROOT / "pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        self.assertEqual(config["project"]["name"], "aws")

    def test_root_pyproject_workstation_core_path(self) -> None:
        """Expected: workstation-core source path is local (no ../)."""
        with open(AWS_ROOT / "pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        path = config["tool"]["uv"]["sources"]["workstation-core"]["path"]
        self.assertFalse(path.startswith(".."), f"path should be local, got: {path}")

    def test_root_uv_lock_exists(self) -> None:
        """Expected: single uv.lock lives at aws/ root."""
        self.assertTrue((AWS_ROOT / "uv.lock").exists())

    def test_uv_lock_has_no_parent_path_references(self) -> None:
        """Expected: lock file contains no ../workstation_core references."""
        content = (AWS_ROOT / "uv.lock").read_text()
        self.assertNotIn("../workstation_core", content)

    def test_gastown_has_no_pyproject(self) -> None:
        """Expected: gastown/ does not have its own pyproject.toml."""
        self.assertFalse((AWS_ROOT / "gastown" / "pyproject.toml").exists())

    def test_gastown_has_no_uv_lock(self) -> None:
        """Expected: gastown/ does not have its own uv.lock."""
        self.assertFalse((AWS_ROOT / "gastown" / "uv.lock").exists())

    def test_builder_has_no_pyproject(self) -> None:
        """Expected: builder/ does not have its own pyproject.toml."""
        self.assertFalse((AWS_ROOT / "builder" / "pyproject.toml").exists())

    def test_builder_has_no_uv_lock(self) -> None:
        """Expected: builder/ does not have its own uv.lock."""
        self.assertFalse((AWS_ROOT / "builder" / "uv.lock").exists())

    def test_dockerfile_single_uv_sync(self) -> None:
        """Expected: Dockerfile runs uv sync exactly once at root."""
        lines = (AWS_ROOT / "Dockerfile").read_text().splitlines()
        sync_lines = [l for l in lines if "uv sync" in l]
        self.assertEqual(len(sync_lines), 1, f"expected 1 uv sync line, got: {sync_lines}")
        self.assertNotIn("cd gastown", sync_lines[0])
        self.assertNotIn("cd builder", sync_lines[0])


if __name__ == "__main__":
    unittest.main()
