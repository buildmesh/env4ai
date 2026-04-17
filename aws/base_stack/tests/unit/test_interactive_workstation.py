"""Unit tests for interactive workstation menu gating behavior.

Moved from gastown/tests/unit/test_interactive_workstation.py.  All logic
under test lives in the shared scripts/interactive_workstation.py and
workstation_core; it is not environment-specific.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from interactive_workstation import _run_action_loop  # noqa: E402
from workstation_core.interactive_workstation import ActionResult, EnvironmentTarget  # noqa: E402
from workstation_core.workstation_status import WorkstationStatus  # noqa: E402


class InteractiveWorkstationScriptTests(unittest.TestCase):
    """Validate script-level state gating and pre-execution policy checks."""

    @staticmethod
    def _environment() -> EnvironmentTarget:
        """Build deterministic environment metadata for script tests."""
        return EnvironmentTarget(
            environment_key="test",
            display_name="Test",
            stack_dir=Path("/tmp/test"),
            stack_name="TestWorkstationStack",
            spot_fleet_logical_id="TestSpotFleet",
            ssh_alias="test-workstation",
            default_access_mode="ssh",
        )

    def test_run_action_loop_blocks_disabled_action_without_dispatch(self) -> None:
        """Failure: selecting a disabled action never dispatches backend work."""
        with (
            patch(
                "interactive_workstation.get_workstation_status",
                side_effect=[
                    WorkstationStatus(stack_state="not found", stack_status=None),
                    WorkstationStatus(stack_state="not found", stack_status=None),
                    WorkstationStatus(stack_state="not found", stack_status=None),
                ],
            ),
            patch("builtins.input", side_effect=["3", "9"]),
            patch("interactive_workstation.dispatch_action", return_value=ActionResult(should_quit=True)) as dispatch,
            patch("builtins.print") as mocked_print,
        ):
            result = _run_action_loop(
                environment=self._environment(),
                cloudformation_client=Mock(),
                ec2_client=Mock(),
            )

        self.assertTrue(result.should_quit)
        self.assertEqual(1, dispatch.call_count)
        dispatched_action = dispatch.call_args.args[0]
        self.assertEqual("quit", dispatched_action)
        rendered = " ".join(str(args[0]) for args, _kwargs in mocked_print.call_args_list if args)
        self.assertIn("Unavailable: deploy the stack first.", rendered)

    def test_run_action_loop_rechecks_state_and_blocks_after_drift(self) -> None:
        """Edge: state drift between render and execute blocks now-invalid action."""
        with (
            patch(
                "interactive_workstation.get_workstation_status",
                side_effect=[
                    WorkstationStatus(stack_state="not found", stack_status=None),
                    WorkstationStatus(stack_state="running", stack_status="CREATE_COMPLETE"),
                    WorkstationStatus(stack_state="running", stack_status="CREATE_COMPLETE"),
                    WorkstationStatus(stack_state="running", stack_status="CREATE_COMPLETE"),
                ],
            ),
            patch("builtins.input", side_effect=["1", "9"]),
            patch("interactive_workstation.dispatch_action", return_value=ActionResult(should_quit=True)) as dispatch,
            patch("builtins.print") as mocked_print,
        ):
            result = _run_action_loop(
                environment=self._environment(),
                cloudformation_client=Mock(),
                ec2_client=Mock(),
            )

        self.assertTrue(result.should_quit)
        self.assertEqual(1, dispatch.call_count)
        dispatched_action = dispatch.call_args.args[0]
        self.assertEqual("quit", dispatched_action)
        rendered = " ".join(str(args[0]) for args, _kwargs in mocked_print.call_args_list if args)
        self.assertIn("Unavailable: stack is already deployed.", rendered)


if __name__ == "__main__":
    unittest.main()
