from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_instance import (
    build_ssh_config_snippet,
    get_region,
    get_newest_instance_for_spot_fleet,
    get_spot_fleet_request_id,
    main,
)


class CheckScriptTests(unittest.TestCase):
    def test_get_region_reads_default_profile_from_config(self) -> None:
        """Expected: default profile region is read from ~/.aws/config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[default]\nregion = us-west-2\n", encoding="utf-8")

            result = get_region(
                cli_region=None,
                cli_profile=None,
                env={},
                config_path=config_path,
            )

        self.assertEqual("us-west-2", result)

    def test_get_region_uses_non_default_profile(self) -> None:
        """Edge: non-default profile section is resolved from CLI profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[profile sandbox]\nregion = us-west-1\n", encoding="utf-8")

            result = get_region(
                cli_region=None,
                cli_profile=" sandbox ",
                env={},
                config_path=config_path,
            )

        self.assertEqual("us-west-1", result)

    def test_get_region_raises_when_unresolvable(self) -> None:
        """Failure: missing config and no CLI/env region raises RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config"
            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS region: ~/.aws/config was not found and no region was provided via --region, AWS_REGION, or AWS_DEFAULT_REGION.",
            ):
                get_region(
                    cli_region=None,
                    cli_profile=None,
                    env={},
                    config_path=missing_config,
                )

    def test_get_region_raises_when_profile_section_missing(self) -> None:
        """Failure: missing profile section in config raises RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[default]\nregion = us-west-2\n", encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS region: profile section '\\[profile sandbox\\]' was not found in ~/.aws/config.",
            ):
                get_region(
                    cli_region=None,
                    cli_profile="sandbox",
                    env={},
                    config_path=config_path,
                )

    def test_get_region_raises_when_profile_has_no_region(self) -> None:
        """Failure: selected profile must include region key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("[default]\noutput = json\n", encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                "Unable to resolve AWS region: no 'region' value found in profile '\\[default\\]' in ~/.aws/config.",
            ):
                get_region(
                    cli_region=None,
                    cli_profile=None,
                    env={},
                    config_path=config_path,
                )

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
                stack_name="BuilderWorkstationStack",
                logical_resource_id="BuilderSpotFleet",
            )

    def test_build_ssh_config_snippet(self) -> None:
        snippet = build_ssh_config_snippet(
            host_alias="builder-workstation",
            ip_address="203.0.113.10",
            ssh_user="ubuntu",
            identity_file="~/.ssh/aws_key.pem",
        )

        self.assertIn("Host builder-workstation", snippet)
        self.assertIn("HostName 203.0.113.10", snippet)
        self.assertIn("User ubuntu", snippet)
        self.assertIn("IdentityFile ~/.ssh/aws_key.pem", snippet)

    def test_main_prints_region_on_success(self) -> None:
        """Expected: resolved region is included in successful output."""
        args = type(
            "Args",
            (),
            {
                "region": "us-west-2",
                "profile": None,
                "stack_name": "BuilderWorkstationStack",
                "spot_fleet_logical_id": "BuilderSpotFleet",
                "ssh_host_alias": "builder-workstation",
                "ssh_user": "ubuntu",
                "identity_file": "~/.ssh/aws_key.pem",
            },
        )()
        session = Mock()
        session.client.side_effect = [Mock(), Mock()]

        with (
            patch("check_instance.parse_args", return_value=args),
            patch("check_instance.get_region", return_value="us-west-2"),
            patch("check_instance.boto3.Session", return_value=session),
            patch("check_instance.get_spot_fleet_request_id", return_value="sfr-123"),
            patch(
                "check_instance.get_newest_instance_for_spot_fleet",
                return_value={
                    "InstanceId": "i-123",
                    "State": {"Name": "running"},
                    "PublicIpAddress": "203.0.113.10",
                },
            ),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            result = main()

        self.assertEqual(0, result)
        self.assertIn("Region: us-west-2", stdout.getvalue())

    def test_main_prints_region_when_instance_has_no_public_ip(self) -> None:
        """Edge: output still includes region before no-public-IP exit."""
        args = type(
            "Args",
            (),
            {
                "region": "us-east-1",
                "profile": None,
                "stack_name": "BuilderWorkstationStack",
                "spot_fleet_logical_id": "BuilderSpotFleet",
                "ssh_host_alias": "builder-workstation",
                "ssh_user": "ubuntu",
                "identity_file": "~/.ssh/aws_key.pem",
            },
        )()
        session = Mock()
        session.client.side_effect = [Mock(), Mock()]

        with (
            patch("check_instance.parse_args", return_value=args),
            patch("check_instance.get_region", return_value="us-east-1"),
            patch("check_instance.boto3.Session", return_value=session),
            patch("check_instance.get_spot_fleet_request_id", return_value="sfr-123"),
            patch(
                "check_instance.get_newest_instance_for_spot_fleet",
                return_value={
                    "InstanceId": "i-456",
                    "State": {"Name": "pending"},
                    "PublicIpAddress": None,
                },
            ),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            result = main()

        self.assertEqual(1, result)
        self.assertIn("Region: us-east-1", stdout.getvalue())

    def test_main_returns_failure_when_region_resolution_fails(self) -> None:
        """Failure: unresolved region returns non-zero and prints error."""
        args = type(
            "Args",
            (),
            {
                "region": None,
                "profile": None,
                "stack_name": "BuilderWorkstationStack",
                "spot_fleet_logical_id": "BuilderSpotFleet",
                "ssh_host_alias": "builder-workstation",
                "ssh_user": "ubuntu",
                "identity_file": "~/.ssh/aws_key.pem",
            },
        )()

        with (
            patch("check_instance.parse_args", return_value=args),
            patch("check_instance.get_region", side_effect=RuntimeError("missing region")),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            result = main()

        self.assertEqual(1, result)
        self.assertIn("Error: missing region", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
