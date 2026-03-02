"""Unit tests for shared runtime/account/region and context resolution."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from workstation_core.runtime_resolution import (
    get_account,
    get_region,
    parse_optional_bool_context,
    parse_optional_text_context,
)


class RuntimeResolutionTests(unittest.TestCase):
    """Validate runtime/account/region resolution helpers."""

    def test_get_region_prefers_cdk_default_region(self) -> None:
        """Expected: explicit CDK_DEFAULT_REGION value wins over config lookup."""
        region = get_region(env={"CDK_DEFAULT_REGION": "us-east-2"})
        self.assertEqual("us-east-2", region)

    def test_get_region_reads_non_default_profile_from_config(self) -> None:
        """Edge: named AWS profile maps to [profile <name>] section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[profile sandbox]\nregion = us-west-1\n", encoding="utf-8")

            region = get_region(
                env={"AWS_PROFILE": "sandbox"},
                config_path=config_path,
            )

        self.assertEqual("us-west-1", region)

    def test_get_region_raises_when_profile_section_missing(self) -> None:
        """Failure: selected profile section must exist in config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[default]\nregion = us-west-2\n", encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS region: profile section '\\[profile sandbox\\]' was not found in ~/.aws/config.",
            ):
                get_region(
                    env={"AWS_PROFILE": "sandbox"},
                    config_path=config_path,
                )

    def test_get_account_prefers_cdk_default_account(self) -> None:
        """Expected: CDK_DEFAULT_ACCOUNT bypasses secret file lookup."""
        account = get_account(env={"CDK_DEFAULT_ACCOUNT": "111122223333"})
        self.assertEqual("111122223333", account)

    def test_parse_optional_text_context_trims_and_handles_none(self) -> None:
        """Edge: optional text context values are normalized consistently."""
        self.assertIsNone(parse_optional_text_context(None))
        self.assertIsNone(parse_optional_text_context("   "))
        self.assertEqual("ami-1234", parse_optional_text_context(" ami-1234 "))

    def test_parse_optional_bool_context_rejects_invalid_value(self) -> None:
        """Failure: unsupported boolean text raises actionable RuntimeError."""
        with self.assertRaisesRegex(
            RuntimeError,
            "Invalid boolean context value for 'bootstrap_on_restored_ami'",
        ):
            parse_optional_bool_context(
                value="sometimes",
                context_key="bootstrap_on_restored_ami",
            )


if __name__ == "__main__":
    unittest.main()
