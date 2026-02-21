from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import app as gastown_app


class RegionResolverTests(unittest.TestCase):
    def test_get_region_reads_default_profile_from_config(self) -> None:
        """Expected: default profile region is loaded from AWS config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[default]\nregion = us-west-2\n", encoding="utf-8")

            region = gastown_app.get_region(env={}, config_path=config_path)

        self.assertEqual("us-west-2", region)

    def test_get_region_uses_non_default_profile_section(self) -> None:
        """Edge: non-default AWS_PROFILE maps to [profile <name>] section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[profile sandbox]\nregion = us-west-1\n", encoding="utf-8")

            region = gastown_app.get_region(
                env={"AWS_PROFILE": "sandbox"}, config_path=config_path
            )

        self.assertEqual("us-west-1", region)

    def test_get_region_raises_when_no_usable_config_region(self) -> None:
        """Failure: missing region key in config profile raises RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[default]\noutput = json\n", encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS region: no 'region' value found in profile '\\[default\\]' in ~/.aws/config.",
            ):
                gastown_app.get_region(env={}, config_path=config_path)

    def test_get_region_raises_when_profile_section_missing(self) -> None:
        """Failure: selected profile section must exist in config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[default]\nregion = us-west-2\n", encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS region: profile section '\\[profile sandbox\\]' was not found in ~/.aws/config.",
            ):
                gastown_app.get_region(
                    env={"AWS_PROFILE": "sandbox"}, config_path=config_path
                )

    def test_get_region_raises_when_config_missing_and_no_env_override(self) -> None:
        """Failure: config file is required when no env region override exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config_path = Path(tmpdir) / "config"
            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS region: ~/.aws/config was not found and CDK_DEFAULT_REGION is not set.",
            ):
                gastown_app.get_region(env={}, config_path=missing_config_path)


if __name__ == "__main__":
    unittest.main()
