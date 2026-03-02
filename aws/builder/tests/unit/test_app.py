from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import app as builder_app
from environment_config import BUILDER_ENVIRONMENT_SPEC


class AppResolverTests(unittest.TestCase):
    def test_main_uses_environment_spec_stack_name(self) -> None:
        """Expected: app.main uses stack name derived from environment spec."""
        app_instance = Mock()
        environment_obj = Mock()

        with (
            patch("app.cdk.App", return_value=app_instance),
            patch("app.cdk.Environment", return_value=environment_obj),
            patch("app.get_account", return_value="111111111111"),
            patch("app.get_region", return_value="us-west-2"),
            patch("app.BuilderWorkstationStack") as stack_mock,
        ):
            builder_app.main()

        stack_mock.assert_called_once_with(
            app_instance,
            BUILDER_ENVIRONMENT_SPEC.stack_name,
            environment_spec=BUILDER_ENVIRONMENT_SPEC,
            env=environment_obj,
        )
        app_instance.synth.assert_called_once()

    def test_get_account_raises_when_env_and_secret_missing(self) -> None:
        """Failure: account resolution fails when env and secret are unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_secret_path = Path(tmpdir) / "aws_acct"
            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS account: CDK_DEFAULT_ACCOUNT is not set and /run/secrets/aws_acct is missing or empty.",
            ):
                builder_app.get_account(env={}, secret_path=missing_secret_path)


if __name__ == "__main__":
    unittest.main()
