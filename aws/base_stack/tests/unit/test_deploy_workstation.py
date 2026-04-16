"""Unit tests for the deploy_workstation wrapper script.

Moved from gastown/tests/unit/test_deploy_workstation.py.  The script lives
in aws/scripts/ and is shared across all environments.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from deploy_workstation import main, parse_args  # noqa: E402
from workstation_core.orchestration import DeployWorkflowInputs  # noqa: E402


class DeployWorkstationScriptTests(unittest.TestCase):
    """Validate thin wrapper behavior for deploy_workstation script."""

    def test_main_delegates_to_shared_orchestration(self) -> None:
        """Expected: wrapper forwards parsed arguments to shared orchestration."""
        with patch("deploy_workstation.run_deploy_lifecycle", return_value=0) as run_flow:
            result = main(
                [
                    "--environment",
                    "test",
                    "--stack-dir",
                    "/tmp/test",
                    "--stack-name",
                    "TestWorkstationStack",
                ]
            )

        self.assertEqual(0, result)
        run_flow.assert_called_once_with(
            DeployWorkflowInputs(
                environment="test",
                stack_dir="/tmp/test",
                stack_name="TestWorkstationStack",
                profile=None,
                region=None,
                access_mode=None,
            )
        )

    def test_parse_args_accepts_optional_region_and_profile(self) -> None:
        """Edge: optional region/profile flags are accepted and returned."""
        args = parse_args(
            [
                "--environment",
                "test",
                "--stack-dir",
                "/tmp/test",
                "--stack-name",
                "TestWorkstationStack",
                "--profile",
                "dev",
                "--region",
                "us-west-2",
            ]
        )

        self.assertEqual("dev", args.profile)
        self.assertEqual("us-west-2", args.region)

    def test_parse_args_accepts_optional_access_mode(self) -> None:
        """Edge: access mode override is accepted and returned."""
        args = parse_args(
            [
                "--environment",
                "test",
                "--stack-dir",
                "/tmp/test",
                "--stack-name",
                "TestWorkstationStack",
                "--access-mode",
                "ssm",
            ]
        )

        self.assertEqual("ssm", args.access_mode)

    def test_main_propagates_orchestration_failures(self) -> None:
        """Failure: orchestration errors are not swallowed by the wrapper."""
        with patch(
            "deploy_workstation.run_deploy_lifecycle",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                main(
                    [
                        "--environment",
                        "test",
                        "--stack-dir",
                        "/tmp/test",
                        "--stack-name",
                        "TestWorkstationStack",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
