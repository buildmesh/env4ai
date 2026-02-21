import configparser
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import app as gastown_app


class AppResolverTests(unittest.TestCase):
    def test_get_region_uses_cdk_default_region(self) -> None:
        region = gastown_app.get_region(env={"CDK_DEFAULT_REGION": " us-east-2 "})
        self.assertEqual("us-east-2", region)

    def test_get_region_uses_non_default_profile_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[profile sandbox]\nregion = us-west-1\n", encoding="utf-8")

            region = gastown_app.get_region(
                env={"AWS_PROFILE": "sandbox"}, config_path=config_path
            )

        self.assertEqual("us-west-1", region)

    def test_get_region_raises_when_config_missing_and_no_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config_path = Path(tmpdir) / "config"
            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS region: ~/.aws/config was not found and CDK_DEFAULT_REGION is not set.",
            ):
                gastown_app.get_region(env={}, config_path=missing_config_path)

    def test_get_region_raises_when_profile_section_missing(self) -> None:
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

    def test_get_region_raises_when_region_key_missing(self) -> None:
        config = configparser.ConfigParser()
        config.read_string("[default]\noutput = json\n")

        with self.assertRaisesRegex(
            RuntimeError,
            "Unable to resolve AWS region: no 'region' value found in profile '\\[default\\]' in ~/.aws/config.",
        ):
            gastown_app.get_region_from_config(config=config, profile_name="default")

    def test_get_account_raises_when_env_and_secret_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_secret_path = Path(tmpdir) / "aws_acct"
            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS account: CDK_DEFAULT_ACCOUNT is not set and /run/secrets/aws_acct is missing or empty.",
            ):
                gastown_app.get_account(env={}, secret_path=missing_secret_path)


if __name__ == "__main__":
    unittest.main()
