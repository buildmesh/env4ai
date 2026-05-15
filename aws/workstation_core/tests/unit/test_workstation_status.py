"""Unit tests for shared workstation status helpers."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from workstation_core.pricing import PriceQuote
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
                purchase_mode="spot",
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

    def test_get_workstation_status_detects_on_demand_purchase_mode(self) -> None:
        """Expected: an existing on-demand CfnInstance resource yields purchase_mode=on_demand."""
        cloudformation_client = Mock()
        ec2_client = Mock()
        cloudformation_client.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}]
        }
        cloudformation_client.describe_stack_resource.return_value = {
            "StackResourceDetail": {"PhysicalResourceId": "i-abc"}
        }
        ec2_client.describe_instances.return_value = {
            "Reservations": [
                {"Instances": [{"InstanceId": "i-abc", "PublicIpAddress": "1.2.3.4"}]}
            ]
        }

        with patch(
            "workstation_core.workstation_status.resolve_running_instance_id",
            return_value="i-abc",
        ):
            result = get_workstation_status(
                cloudformation_client,
                ec2_client,
                stack_name="GastownWorkstationStack",
                spot_fleet_logical_id="GastownSpotFleet",
                ssh_alias="gastown-workstation",
                instance_logical_id="GastownInstance",
            )

        self.assertEqual("on_demand", result.purchase_mode)

    def test_get_workstation_status_invokes_price_provider_when_provided(self) -> None:
        """Expected: a configured provider populates price_quote for the running instance."""
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
                            "InstanceId": "i-spot",
                            "PublicIpAddress": "1.2.3.4",
                            "Placement": {"AvailabilityZone": "us-west-2a"},
                        }
                    ]
                }
            ]
        }
        seen_args: list[tuple[str, str | None]] = []

        def provider(purchase_mode: str, az: str | None) -> PriceQuote:
            seen_args.append((purchase_mode, az))
            return PriceQuote(
                purchase_mode=purchase_mode,
                current_price_per_hour="0.0234",
                spot_price_limit="0.10",
                availability_zone=az,
            )

        with patch(
            "workstation_core.workstation_status.resolve_running_instance_id",
            return_value="i-spot",
        ):
            result = get_workstation_status(
                cloudformation_client,
                ec2_client,
                stack_name="GastownWorkstationStack",
                spot_fleet_logical_id="GastownSpotFleet",
                ssh_alias="gastown-workstation",
                price_provider=provider,
            )

        self.assertEqual([("spot", "us-west-2a")], seen_args)
        self.assertIsNotNone(result.price_quote)
        self.assertEqual("0.0234", result.price_quote.current_price_per_hour)

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
