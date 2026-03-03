"""Unit tests for shared workstation status helpers."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from workstation_core.workstation_status import WorkstationStatus, get_workstation_status


class WorkstationStatusTests(unittest.TestCase):
    """Validate interactive workstation status resolution."""

    def test_get_workstation_status_returns_running_metadata(self) -> None:
        """Expected: running stack includes instance metadata and SSH alias."""
        cloudformation_client = Mock()
        ec2_client = Mock()
        cloudformation_client.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}]
        }
        ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-123",
                            "PublicIpAddress": "1.2.3.4",
                        }
                    ]
                }
            ]
        }

        with patch(
            "workstation_core.workstation_status.resolve_running_instance_id",
            return_value="i-123",
        ):
            result = get_workstation_status(
                cloudformation_client,
                ec2_client,
                stack_name="GastownWorkstationStack",
                spot_fleet_logical_id="GastownSpotFleet",
                ssh_alias="gastown-workstation",
            )

        self.assertEqual(
            WorkstationStatus(
                stack_state="running",
                stack_status="CREATE_COMPLETE",
                instance_id="i-123",
                public_ip="1.2.3.4",
                ssh_alias="gastown-workstation",
            ),
            result,
        )

    def test_get_workstation_status_returns_in_progress_without_running_instance(self) -> None:
        """Edge: complete stack without a running instance reports in-progress state."""
        cloudformation_client = Mock()
        ec2_client = Mock()
        cloudformation_client.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}]
        }

        with patch(
            "workstation_core.workstation_status.resolve_running_instance_id",
            side_effect=RuntimeError("No running instances found for stack Spot Fleet."),
        ):
            result = get_workstation_status(
                cloudformation_client,
                ec2_client,
                stack_name="GastownWorkstationStack",
                spot_fleet_logical_id="GastownSpotFleet",
                ssh_alias="gastown-workstation",
            )

        self.assertEqual("in progress", result.stack_state)
        self.assertEqual("CREATE_COMPLETE", result.stack_status)
        self.assertIsNone(result.instance_id)

    def test_get_workstation_status_raises_for_aws_lookup_errors(self) -> None:
        """Failure: unexpected AWS lookup errors surface actionable runtime errors."""
        cloudformation_client = Mock()
        ec2_client = Mock()
        cloudformation_client.describe_stacks.side_effect = RuntimeError("boom")

        with self.assertRaisesRegex(
            RuntimeError, "Failed to read stack status for 'GastownWorkstationStack'."
        ):
            get_workstation_status(
                cloudformation_client,
                ec2_client,
                stack_name="GastownWorkstationStack",
                spot_fleet_logical_id="GastownSpotFleet",
                ssh_alias="gastown-workstation",
            )


if __name__ == "__main__":
    unittest.main()
