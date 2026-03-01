from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import app as gastown_app


class AppResolverTests(unittest.TestCase):
    def test_get_account_raises_when_env_and_secret_missing(self) -> None:
        """Failure: account resolution fails when env and secret are unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_secret_path = Path(tmpdir) / "aws_acct"
            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS account: CDK_DEFAULT_ACCOUNT is not set and /run/secrets/aws_acct is missing or empty.",
            ):
                gastown_app.get_account(env={}, secret_path=missing_secret_path)

    def test_parse_optional_bool_context_true_variants(self) -> None:
        """Expected: parser accepts common true values for context flags."""
        self.assertTrue(
            gastown_app.parse_optional_bool_context(
                value="true",
                context_key="bootstrap_on_restored_ami",
            )
        )

    def test_parse_optional_bool_context_false_with_whitespace(self) -> None:
        """Edge: parser trims whitespace around false-like values."""
        self.assertFalse(
            gastown_app.parse_optional_bool_context(
                value="  off  ",
                context_key="bootstrap_on_restored_ami",
            )
        )

    def test_parse_optional_bool_context_rejects_invalid_value(self) -> None:
        """Failure: invalid context value raises with actionable guidance."""
        with self.assertRaisesRegex(
            RuntimeError,
            "Invalid boolean context value for 'bootstrap_on_restored_ami'",
        ):
            gastown_app.parse_optional_bool_context(
                value="sometimes",
                context_key="bootstrap_on_restored_ami",
            )

    def test_main_uses_default_bootstrap_path_when_ami_context_missing(self) -> None:
        """Expected: app.main passes no AMI override when context is absent."""
        app_instance = Mock()
        app_instance.node.try_get_context.return_value = None
        environment_obj = Mock()

        with (
            patch("app.cdk.App", return_value=app_instance),
            patch("app.cdk.Environment", return_value=environment_obj),
            patch("app.get_account", return_value="111111111111"),
            patch("app.get_region", return_value="us-west-2"),
            patch("app.GastownWorkstationStack") as stack_mock,
        ):
            gastown_app.main()

        stack_mock.assert_called_once_with(
            app_instance,
            "GastownWorkstationStack",
            ami_id_override=None,
            env=environment_obj,
        )
        app_instance.synth.assert_called_once()

    def test_main_uses_trimmed_ami_override_when_context_present(self) -> None:
        """Edge: app.main trims context AMI value before passing override."""
        app_instance = Mock()
        app_instance.node.try_get_context.return_value = " ami-override123 "
        environment_obj = Mock()

        with (
            patch("app.cdk.App", return_value=app_instance),
            patch("app.cdk.Environment", return_value=environment_obj),
            patch("app.get_account", return_value="111111111111"),
            patch("app.get_region", return_value="us-west-2"),
            patch("app.GastownWorkstationStack") as stack_mock,
        ):
            gastown_app.main()

        stack_mock.assert_called_once_with(
            app_instance,
            "GastownWorkstationStack",
            ami_id_override="ami-override123",
            env=environment_obj,
        )
        app_instance.synth.assert_called_once()

    def test_main_propagates_account_resolution_failure(self) -> None:
        """Failure: account resolution error bubbles up and aborts synth."""
        app_instance = Mock()
        app_instance.node.try_get_context.return_value = None

        with (
            patch("app.cdk.App", return_value=app_instance),
            patch("app.get_account", side_effect=RuntimeError("missing account")),
            patch("app.GastownWorkstationStack") as stack_mock,
        ):
            with self.assertRaisesRegex(RuntimeError, "missing account"):
                gastown_app.main()

        stack_mock.assert_not_called()
        app_instance.synth.assert_not_called()


if __name__ == "__main__":
    unittest.main()
