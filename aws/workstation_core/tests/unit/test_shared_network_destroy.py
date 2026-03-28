"""Unit tests for shared-network destroy orchestration."""

from __future__ import annotations

import io
import unittest
from unittest.mock import Mock, patch

from workstation_core.orchestration import destroy_shared_network_stack


class SharedNetworkDestroyTests(unittest.TestCase):
    """Validate preflight and destroy flow for Env4aiNetworkStack."""

    def test_destroy_shared_network_stack_returns_noop_when_stack_is_missing(self) -> None:
        """Edge: missing shared stack exits cleanly with an actionable message."""
        session = Mock()
        session.region_name = "us-west-2"
        session.client.return_value = Mock()
        out = io.StringIO()

        with (
            patch("workstation_core.orchestration.boto3.Session", return_value=session),
            patch("workstation_core.orchestration._list_stack_names", return_value=set()),
            patch("workstation_core.orchestration.run_command") as run_command,
        ):
            result = destroy_shared_network_stack(profile=None, region=None, out=out)

        self.assertEqual(0, result)
        self.assertIn("does not exist; nothing to destroy", out.getvalue())
        run_command.assert_not_called()

    def test_destroy_shared_network_stack_blocks_when_environment_stacks_still_exist(self) -> None:
        """Failure: active workstation stacks prevent shared-network teardown."""
        session = Mock()
        session.region_name = "us-west-2"
        session.client.return_value = Mock()

        with (
            patch("workstation_core.orchestration.boto3.Session", return_value=session),
            patch(
                "workstation_core.orchestration._list_stack_names",
                return_value={"Env4aiNetworkStack", "GastownWorkstationStack"},
            ),
            patch(
                "workstation_core.orchestration._discover_environment_stack_names",
                return_value={"GastownWorkstationStack", "BuilderWorkstationStack"},
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Cannot destroy Env4aiNetworkStack while environment stacks still exist: GastownWorkstationStack",
            ):
                destroy_shared_network_stack(profile=None, region=None)

    def test_destroy_shared_network_stack_runs_cdk_destroy_after_preflight(self) -> None:
        """Expected: destroy proceeds once the shared stack is the only remaining dependency."""
        session = Mock()
        session.region_name = "us-west-2"
        session.client.return_value = Mock()
        out = io.StringIO()

        with (
            patch("workstation_core.orchestration.boto3.Session", return_value=session),
            patch(
                "workstation_core.orchestration._list_stack_names",
                return_value={"Env4aiNetworkStack"},
            ),
            patch(
                "workstation_core.orchestration._discover_environment_stack_names",
                return_value={"GastownWorkstationStack"},
            ),
            patch(
                "workstation_core.orchestration._resolve_stack_dir",
                return_value="/tmp/env-stack",
            ),
            patch("workstation_core.orchestration.run_command") as run_command,
        ):
            result = destroy_shared_network_stack(profile="dev", region="us-west-2", out=out)

        self.assertEqual(0, result)
        run_command.assert_called_once_with(
            ["uv", "run", "cdk", "destroy", "--force", "Env4aiNetworkStack"],
            cwd="/tmp/env-stack",
            timeout_seconds=45 * 60,
        )
        self.assertIn("Destroyed Env4aiNetworkStack.", out.getvalue())


if __name__ == "__main__":
    unittest.main()
