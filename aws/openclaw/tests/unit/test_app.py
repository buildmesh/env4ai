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


if __name__ == "__main__":
    unittest.main()
