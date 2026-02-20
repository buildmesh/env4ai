from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_instance import (
    build_ssh_config_snippet,
    get_newest_instance_for_spot_fleet,
    get_spot_fleet_request_id,
)


class CheckScriptTests(unittest.TestCase):
    def test_get_newest_instance_for_spot_fleet_returns_latest_launch_time(self) -> None:
        ec2_client = Mock()
        ec2_client.describe_spot_fleet_instances.return_value = {
            "ActiveInstances": [
                {"InstanceId": "i-older"},
                {"InstanceId": "i-newer"},
            ]
        }
        ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-older",
                            "LaunchTime": datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
                            "PublicIpAddress": "1.1.1.1",
                        },
                        {
                            "InstanceId": "i-newer",
                            "LaunchTime": datetime(2026, 2, 20, 10, 5, tzinfo=timezone.utc),
                            "PublicIpAddress": "2.2.2.2",
                        },
                    ]
                }
            ]
        }

        result = get_newest_instance_for_spot_fleet(ec2_client, "sfr-123")

        self.assertEqual("i-newer", result["InstanceId"])

    def test_get_newest_instance_for_spot_fleet_raises_when_no_active_instances(self) -> None:
        ec2_client = Mock()
        ec2_client.describe_spot_fleet_instances.return_value = {"ActiveInstances": []}

        with self.assertRaises(RuntimeError):
            get_newest_instance_for_spot_fleet(ec2_client, "sfr-123")

    def test_get_spot_fleet_request_id_raises_on_cloudformation_error(self) -> None:
        cloudformation_client = Mock()
        cloudformation_client.describe_stack_resource.side_effect = ClientError(
            error_response={"Error": {"Code": "ValidationError", "Message": "bad request"}},
            operation_name="DescribeStackResource",
        )

        with self.assertRaises(RuntimeError):
            get_spot_fleet_request_id(
                cloudformation_client=cloudformation_client,
                stack_name="AwsWorkstationStack",
                logical_resource_id="WorkstationSpotFleet",
            )

    def test_build_ssh_config_snippet(self) -> None:
        snippet = build_ssh_config_snippet(
            host_alias="gastown-workstation",
            ip_address="203.0.113.10",
            ssh_user="ubuntu",
            identity_file="~/.ssh/aws_key.pem",
        )

        self.assertIn("Host gastown-workstation", snippet)
        self.assertIn("HostName 203.0.113.10", snippet)
        self.assertIn("User ubuntu", snippet)
        self.assertIn("IdentityFile ~/.ssh/aws_key.pem", snippet)


if __name__ == "__main__":
    unittest.main()
