"""Structural tests for launcher bootstrap helpers."""

from __future__ import annotations

from pathlib import Path
import unittest


AWS_ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_DEPS = AWS_ROOT / "launcher" / "init" / "deps.sh"


class LauncherDepsTests(unittest.TestCase):
    """Validate the generated launcher-local SSM helper script."""

    @staticmethod
    def _deps_content() -> str:
        """Return the checked-in launcher deps bootstrap content."""
        return (
            LAUNCHER_DEPS.read_text(encoding="utf-8")
            .replace("\\$", "$")
            .replace('\\"', '"')
        )

    def test_ssm_helper_validates_required_environment_argument(self) -> None:
        """Expected: the helper refuses to run without exactly one target name."""
        content = self._deps_content()

        self.assertIn('if [ "$#" -ne 1 ] || [ -z "$1" ]; then', content)
        self.assertIn('echo "Usage: ssm <environment-name>" >&2', content)

    def test_ssm_helper_resolves_region_dynamically(self) -> None:
        """Edge: the helper derives region from AWS runtime configuration."""
        content = self._deps_content()

        self.assertIn('configured_region=$(aws configure get region 2>/dev/null || true)', content)
        self.assertIn('region=$(printf \'%s\' "${AWS_REGION:-${AWS_DEFAULT_REGION:-$configured_region}}"', content)
        self.assertIn('--region "$region"', content)
        self.assertNotIn('--region us-west-2', content)

    def test_ssm_helper_rejects_empty_instance_lookup_and_execs_session(self) -> None:
        """Failure: invalid instance lookups fail clearly before starting the session."""
        content = self._deps_content()

        self.assertIn('if [ -z "$instance_id" ] || [ "$instance_id" = "None" ] || [ "$instance_id" = "null" ]; then', content)
        self.assertIn('echo "Unable to find a running instance named', content)
        self.assertIn('exec aws ssm start-session --region "$region" --target "$instance_id"', content)


if __name__ == "__main__":
    unittest.main()
