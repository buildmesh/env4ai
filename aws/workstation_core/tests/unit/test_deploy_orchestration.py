"""Unit tests for shared deploy orchestration workflows."""

from __future__ import annotations

import io
import unittest
from unittest.mock import Mock, patch

from workstation_core.orchestration import DeployWorkflowInputs, run_deploy_lifecycle


class DeployOrchestrationTests(unittest.TestCase):
    """Validate shared deploy orchestration behavior."""

    @staticmethod
    def _inputs() -> DeployWorkflowInputs:
        """Return common test inputs."""
        return DeployWorkflowInputs(
            environment="gastown",
            stack_dir="/tmp/gastown",
            stack_name="GastownWorkstationStack",
            profile=None,
            region=None,
            access_mode=None,
        )

    def test_run_deploy_lifecycle_runs_default_deploy_path_without_ami_flags(self) -> None:
        """Expected: no AMI controls triggers default deploy + post check flow with EIP."""
        env = {"AWS_REGION": "us-west-2"}
        selection = Mock(should_deploy=True, selected_ami_id=None)
        eip_info = {"allocation_id": "eipalloc-abc123", "public_ip": "1.2.3.4"}

        with (
            patch("workstation_core.orchestration.make_ec2_client", return_value=Mock()),
            patch("workstation_core.orchestration.resolve_ami_selection", return_value=selection),
            patch("workstation_core.orchestration.shared_network_stack_exists", return_value=False),
            patch("workstation_core.orchestration.find_or_create_eip", return_value=eip_info),
            patch("workstation_core.orchestration.deploy_shared_network_stack") as deploy_shared_network_stack,
            patch("workstation_core.orchestration.deploy_stack") as deploy_stack,
            patch("workstation_core.orchestration.run_post_deploy_check") as post_check,
        ):
            result = run_deploy_lifecycle(inputs=self._inputs(), env=env, out=io.StringIO())

        self.assertEqual(0, result)
        deploy_shared_network_stack.assert_called_once_with(stack_dir="/tmp/gastown")
        deploy_stack.assert_called_once_with(
            stack_dir="/tmp/gastown",
            stack_name="GastownWorkstationStack",
            ami_id=None,
            bootstrap_on_restored_ami=False,
            eip_allocation_id="eipalloc-abc123",
            access_mode="ssh",
        )
        post_check.assert_called_once_with(
            stack_dir="/tmp/gastown",
            stack_name="GastownWorkstationStack",
            eip_allocation_id="eipalloc-abc123",
            eip_public_ip="1.2.3.4",
            access_mode="ssh",
        )

    def test_run_deploy_lifecycle_deploys_shared_network_when_missing(self) -> None:
        """Expected: first-use deploy creates the shared network before the workstation."""
        env = {"AWS_REGION": "us-west-2"}
        selection = Mock(should_deploy=True, selected_ami_id=None)
        eip_info = {"allocation_id": "eipalloc-abc123", "public_ip": "1.2.3.4"}

        with (
            patch("workstation_core.orchestration.make_ec2_client", return_value=Mock()),
            patch("workstation_core.orchestration.resolve_ami_selection", return_value=selection),
            patch("workstation_core.orchestration.shared_network_stack_exists", return_value=False),
            patch("workstation_core.orchestration.find_or_create_eip", return_value=eip_info),
            patch("workstation_core.orchestration.deploy_shared_network_stack") as deploy_shared_network_stack,
            patch("workstation_core.orchestration.deploy_stack") as deploy_stack,
            patch("workstation_core.orchestration.run_post_deploy_check"),
        ):
            result = run_deploy_lifecycle(inputs=self._inputs(), env=env, out=io.StringIO())

        self.assertEqual(0, result)
        deploy_shared_network_stack.assert_called_once_with(stack_dir="/tmp/gastown")
        deploy_stack.assert_called_once()

    def test_run_deploy_lifecycle_skips_shared_network_deploy_when_stack_exists(self) -> None:
        """Expected: routine deploys leave the shared network stack untouched."""
        env = {"AWS_REGION": "us-west-2"}
        selection = Mock(should_deploy=True, selected_ami_id=None)
        eip_info = {"allocation_id": "eipalloc-abc123", "public_ip": "1.2.3.4"}

        with (
            patch("workstation_core.orchestration.make_ec2_client", return_value=Mock()),
            patch("workstation_core.orchestration.resolve_ami_selection", return_value=selection),
            patch("workstation_core.orchestration.shared_network_stack_exists", return_value=True),
            patch("workstation_core.orchestration.find_or_create_eip", return_value=eip_info),
            patch("workstation_core.orchestration.deploy_shared_network_stack") as deploy_shared_network_stack,
            patch("workstation_core.orchestration.deploy_stack") as deploy_stack,
            patch("workstation_core.orchestration.run_post_deploy_check"),
        ):
            result = run_deploy_lifecycle(inputs=self._inputs(), env=env, out=io.StringIO())

        self.assertEqual(0, result)
        deploy_shared_network_stack.assert_not_called()
        deploy_stack.assert_called_once()

    def test_run_deploy_lifecycle_prefers_cli_access_mode(self) -> None:
        """Expected: CLI access mode override wins over env and environment defaults."""
        env = {"AWS_REGION": "us-west-2", "ACCESS_MODE": "ssh"}
        selection = Mock(should_deploy=True, selected_ami_id=None)
        eip_info = {"allocation_id": "eipalloc-abc123", "public_ip": "1.2.3.4"}
        environment_spec = Mock(environment_key="gastown", default_access_mode="both")

        with (
            patch("workstation_core.orchestration.load_environment_spec", return_value=environment_spec),
            patch("workstation_core.orchestration.make_ec2_client", return_value=Mock()),
            patch("workstation_core.orchestration.resolve_ami_selection", return_value=selection),
            patch("workstation_core.orchestration.shared_network_stack_exists", return_value=False),
            patch("workstation_core.orchestration.find_or_create_eip", return_value=eip_info),
            patch("workstation_core.orchestration.deploy_shared_network_stack"),
            patch("workstation_core.orchestration.deploy_stack") as deploy_stack,
            patch("workstation_core.orchestration.run_post_deploy_check"),
        ):
            result = run_deploy_lifecycle(
                inputs=DeployWorkflowInputs(
                    environment="gastown",
                    stack_dir="/tmp/gastown",
                    stack_name="GastownWorkstationStack",
                    access_mode="ssm",
                ),
                env=env,
                out=io.StringIO(),
            )

        self.assertEqual(0, result)
        self.assertEqual("ssm", deploy_stack.call_args.kwargs["access_mode"])

    def test_run_deploy_lifecycle_exits_early_for_list_only_mode(self) -> None:
        """Edge: AMI list-only mode does not invoke deploy or post-check commands."""
        env = {"AWS_REGION": "us-west-2", "AMI_LIST": "1"}
        selection = Mock(should_deploy=False, selected_ami_id=None)

        with (
            patch("workstation_core.orchestration.make_ec2_client", return_value=Mock()),
            patch("workstation_core.orchestration.resolve_ami_selection", return_value=selection),
            patch("workstation_core.orchestration.deploy_shared_network_stack") as deploy_shared_network_stack,
            patch("workstation_core.orchestration.deploy_stack") as deploy_stack,
            patch("workstation_core.orchestration.run_post_deploy_check") as post_check,
        ):
            result = run_deploy_lifecycle(inputs=self._inputs(), env=env, out=io.StringIO())

        self.assertEqual(0, result)
        deploy_shared_network_stack.assert_not_called()
        deploy_stack.assert_not_called()
        post_check.assert_not_called()

    def test_run_deploy_lifecycle_propagates_ami_resolution_failure(self) -> None:
        """Failure: AMI selection failures abort orchestration before deploy mutation."""
        env = {"AWS_REGION": "us-west-2", "AMI_LOAD": "missing"}

        with (
            patch("workstation_core.orchestration.make_ec2_client", return_value=Mock()),
            patch(
                "workstation_core.orchestration.resolve_ami_selection",
                side_effect=RuntimeError("Requested AMI 'gastown_missing' was not found."),
            ),
            patch("workstation_core.orchestration.find_or_create_eip") as find_or_create_eip,
            patch("workstation_core.orchestration.deploy_shared_network_stack") as deploy_shared_network_stack,
            patch("workstation_core.orchestration.deploy_stack") as deploy_stack,
        ):
            with self.assertRaisesRegex(RuntimeError, "Requested AMI 'gastown_missing' was not found."):
                run_deploy_lifecycle(inputs=self._inputs(), env=env, out=io.StringIO())

        find_or_create_eip.assert_not_called()
        deploy_shared_network_stack.assert_not_called()
        deploy_stack.assert_not_called()

    def test_run_deploy_lifecycle_aborts_environment_deploy_when_shared_network_deploy_fails(self) -> None:
        """Failure: shared network deploy errors stop the environment deploy flow."""
        env = {"AWS_REGION": "us-west-2"}
        selection = Mock(should_deploy=True, selected_ami_id=None)

        with (
            patch("workstation_core.orchestration.make_ec2_client", return_value=Mock()),
            patch("workstation_core.orchestration.resolve_ami_selection", return_value=selection),
            patch("workstation_core.orchestration.find_or_create_eip") as find_or_create_eip,
            patch("workstation_core.orchestration.shared_network_stack_exists", return_value=False),
            patch(
                "workstation_core.orchestration.deploy_shared_network_stack",
                side_effect=RuntimeError("network deploy failed"),
            ),
            patch("workstation_core.orchestration.deploy_stack") as deploy_stack,
        ):
            with self.assertRaisesRegex(RuntimeError, "network deploy failed"):
                run_deploy_lifecycle(inputs=self._inputs(), env=env, out=io.StringIO())

        find_or_create_eip.assert_not_called()
        deploy_stack.assert_not_called()


if __name__ == "__main__":
    unittest.main()
