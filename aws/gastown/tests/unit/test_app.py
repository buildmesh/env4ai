from pathlib import Path
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
