"""Unit tests for base_stack/app.py.

Consolidated from builder/tests/unit/test_app.py and
gastown/tests/unit/test_app.py, which were identical in structure but
duplicated for each environment.
"""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
_BASE_STACK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_FIXTURES))
sys.path.insert(0, str(_BASE_STACK))

import app as base_app
from environment_config import ENVIRONMENT_SPEC


class AppResolverTests(unittest.TestCase):
    def test_get_account_raises_when_env_and_secret_missing(self) -> None:
        """Failure: account resolution fails when env and secret are unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_secret_path = Path(tmpdir) / "aws_acct"
            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS account: CDK_DEFAULT_ACCOUNT is not set and /run/secrets/aws_acct is missing or empty.",
            ):
                base_app.get_account(env={}, secret_path=missing_secret_path)

    def test_parse_optional_bool_context_true_variants(self) -> None:
        """Expected: parser accepts common true values for context flags."""
        self.assertTrue(
            base_app.parse_optional_bool_context(
                value="true",
                context_key="bootstrap_on_restored_ami",
            )
        )

    def test_parse_optional_bool_context_false_with_whitespace(self) -> None:
        """Edge: parser trims whitespace around false-like values."""
        self.assertFalse(
            base_app.parse_optional_bool_context(
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
            base_app.parse_optional_bool_context(
                value="sometimes",
                context_key="bootstrap_on_restored_ami",
            )

    def test_main_uses_default_bootstrap_path_when_ami_context_missing(self) -> None:
        """Expected: app.main passes no AMI override when context is absent."""
        app_instance = Mock()
        app_instance.node.try_get_context.side_effect = lambda _key: None
        environment_obj = Mock()

        with (
            patch("app.cdk.App", return_value=app_instance),
            patch("app.cdk.Environment", return_value=environment_obj),
            patch("app.get_account", return_value="111111111111"),
            patch("app.get_region", return_value="us-west-2"),
            patch("app.WorkstationStack") as stack_mock,
        ):
            base_app.main()

        stack_mock.assert_called_once_with(
            app_instance,
            ENVIRONMENT_SPEC.stack_name,
            ami_id_override=None,
            bootstrap_on_restored_ami=False,
            verbose_bootstrap_resolution=False,
            eip_allocation_id=None,
            environment_spec=ENVIRONMENT_SPEC,
            env=environment_obj,
        )
        app_instance.synth.assert_called_once()

    def test_main_uses_trimmed_ami_override_when_context_present(self) -> None:
        """Edge: app.main trims context AMI value before passing override."""
        app_instance = Mock()
        app_instance.node.try_get_context.side_effect = (
            lambda key: " ami-override123 " if key == "ami_id" else None
        )
        environment_obj = Mock()

        with (
            patch("app.cdk.App", return_value=app_instance),
            patch("app.cdk.Environment", return_value=environment_obj),
            patch("app.get_account", return_value="111111111111"),
            patch("app.get_region", return_value="us-west-2"),
            patch("app.WorkstationStack") as stack_mock,
        ):
            base_app.main()

        stack_mock.assert_called_once_with(
            app_instance,
            ENVIRONMENT_SPEC.stack_name,
            ami_id_override="ami-override123",
            bootstrap_on_restored_ami=False,
            verbose_bootstrap_resolution=False,
            eip_allocation_id=None,
            environment_spec=ENVIRONMENT_SPEC,
            env=environment_obj,
        )
        app_instance.synth.assert_called_once()

    def test_main_enables_verbose_bootstrap_resolution_from_context(self) -> None:
        """Expected: verbose bootstrap context is parsed and passed to the stack."""
        app_instance = Mock()
        app_instance.node.try_get_context.side_effect = (
            lambda key: "true" if key == "verbose_bootstrap_resolution" else None
        )
        environment_obj = Mock()

        with (
            patch("app.cdk.App", return_value=app_instance),
            patch("app.cdk.Environment", return_value=environment_obj),
            patch("app.get_account", return_value="111111111111"),
            patch("app.get_region", return_value="us-west-2"),
            patch("app.WorkstationStack") as stack_mock,
        ):
            base_app.main()

        stack_mock.assert_called_once_with(
            app_instance,
            ENVIRONMENT_SPEC.stack_name,
            ami_id_override=None,
            bootstrap_on_restored_ami=False,
            verbose_bootstrap_resolution=True,
            eip_allocation_id=None,
            environment_spec=ENVIRONMENT_SPEC,
            env=environment_obj,
        )
        app_instance.synth.assert_called_once()

    def test_main_propagates_account_resolution_failure(self) -> None:
        """Failure: account resolution error bubbles up and aborts synth."""
        app_instance = Mock()
        app_instance.node.try_get_context.side_effect = lambda _key: None

        with (
            patch("app.cdk.App", return_value=app_instance),
            patch("app.get_account", side_effect=RuntimeError("missing account")),
            patch("app.WorkstationStack") as stack_mock,
        ):
            with self.assertRaisesRegex(RuntimeError, "missing account"):
                base_app.main()

        stack_mock.assert_not_called()
        app_instance.synth.assert_not_called()


if __name__ == "__main__":
    unittest.main()
