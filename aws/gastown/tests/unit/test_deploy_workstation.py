import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from deploy_workstation import (  # noqa: E402
    build_ami_lookup_error_message,
    deploy_stack,
    list_environment_images,
    main,
    pick_image_interactively,
    resolve_exact_image_id,
    run_command,
    run_ami_permission_preflight,
    validate_mode_arguments,
)


class DeployWorkstationScriptTests(unittest.TestCase):
    @staticmethod
    def _args() -> object:
        """Build common argument payload used by main-flow tests."""
        return type(
            "Args",
            (),
            {
                "environment": "gastown",
                "stack_dir": "/tmp/gastown",
                "stack_name": "GastownWorkstationStack",
                "profile": None,
                "region": None,
            },
        )()

    def test_main_deploys_default_path_when_no_ami_controls(self) -> None:
        """Expected: baseline deploy path skips AMI selection and deploys normally."""
        ec2_client = Mock()
        with (
            patch("deploy_workstation.parse_args", return_value=self._args()),
            patch.dict(
                "deploy_workstation.os.environ",
                {"AWS_REGION": "us-west-2"},
                clear=True,
            ),
            patch("deploy_workstation.make_ec2_client", return_value=ec2_client),
            patch("deploy_workstation.deploy_stack") as deploy_stack_mock,
            patch("deploy_workstation.run_post_deploy_check") as post_check_mock,
        ):
            result = main()

        self.assertEqual(0, result)
        deploy_stack_mock.assert_called_once_with(stack_dir="/tmp/gastown", ami_id=None)
        post_check_mock.assert_called_once_with(
            stack_dir="/tmp/gastown",
            stack_name="GastownWorkstationStack",
        )

    def test_main_loads_exact_ami_when_ami_load_tag_is_set(self) -> None:
        """Expected: AMI_LOAD resolves exact tag name and deploys with that AMI ID."""
        ec2_client = Mock()
        with (
            patch("deploy_workstation.parse_args", return_value=self._args()),
            patch.dict(
                "deploy_workstation.os.environ",
                {"AWS_REGION": "us-west-2", "AMI_LOAD": "20260301"},
                clear=True,
            ),
            patch("deploy_workstation.make_ec2_client", return_value=ec2_client),
            patch("deploy_workstation.resolve_exact_image_id", return_value="ami-load"),
            patch("deploy_workstation.deploy_stack") as deploy_stack_mock,
            patch("deploy_workstation.run_post_deploy_check") as post_check_mock,
        ):
            result = main()

        self.assertEqual(0, result)
        deploy_stack_mock.assert_called_once_with(stack_dir="/tmp/gastown", ami_id="ami-load")
        post_check_mock.assert_called_once_with(
            stack_dir="/tmp/gastown",
            stack_name="GastownWorkstationStack",
        )

    def test_main_raises_when_ami_load_tag_does_not_exist(self) -> None:
        """Failure: AMI_LOAD aborts deploy when the exact AMI lookup fails."""
        ec2_client = Mock()
        with (
            patch("deploy_workstation.parse_args", return_value=self._args()),
            patch.dict(
                "deploy_workstation.os.environ",
                {"AWS_REGION": "us-west-2", "AMI_LOAD": "missing"},
                clear=True,
            ),
            patch("deploy_workstation.make_ec2_client", return_value=ec2_client),
            patch(
                "deploy_workstation.resolve_exact_image_id",
                side_effect=RuntimeError("Requested AMI 'gastown_missing' was not found."),
            ),
            patch("deploy_workstation.deploy_stack") as deploy_stack_mock,
        ):
            with self.assertRaisesRegex(RuntimeError, "Requested AMI 'gastown_missing' was not found."):
                main()

        deploy_stack_mock.assert_not_called()

    def test_main_lists_images_and_exits_without_deploy_when_pick_disabled(self) -> None:
        """Edge: AMI_LIST without AMI_PICK lists entries and skips deployment."""
        ec2_client = Mock()
        listed_images = [
            {
                "image_id": "ami-list",
                "name": "gastown_saved",
                "state": "available",
                "creation_date": "2026-02-15T00:00:00.000Z",
            }
        ]
        with (
            patch("deploy_workstation.parse_args", return_value=self._args()),
            patch.dict(
                "deploy_workstation.os.environ",
                {"AWS_REGION": "us-west-2", "AMI_LIST": "1"},
                clear=True,
            ),
            patch("deploy_workstation.make_ec2_client", return_value=ec2_client),
            patch("deploy_workstation.list_environment_images", return_value=listed_images),
            patch("deploy_workstation.print_image_list") as print_image_list_mock,
            patch("deploy_workstation.deploy_stack") as deploy_stack_mock,
            patch("deploy_workstation.run_post_deploy_check") as post_check_mock,
        ):
            result = main()

        self.assertEqual(0, result)
        print_image_list_mock.assert_called_once_with(listed_images)
        deploy_stack_mock.assert_not_called()
        post_check_mock.assert_not_called()

    def test_main_deploys_selected_image_when_list_and_pick_enabled(self) -> None:
        """Expected: AMI_LIST+AMI_PICK deploys using the chosen environment AMI."""
        ec2_client = Mock()
        listed_images = [
            {
                "image_id": "ami-a",
                "name": "gastown_a",
                "state": "available",
                "creation_date": "2026-02-15T00:00:00.000Z",
            },
            {
                "image_id": "ami-b",
                "name": "gastown_b",
                "state": "available",
                "creation_date": "2026-02-16T00:00:00.000Z",
            },
        ]
        selected_image = listed_images[1]
        with (
            patch("deploy_workstation.parse_args", return_value=self._args()),
            patch.dict(
                "deploy_workstation.os.environ",
                {"AWS_REGION": "us-west-2", "AMI_LIST": "1", "AMI_PICK": "1"},
                clear=True,
            ),
            patch("deploy_workstation.make_ec2_client", return_value=ec2_client),
            patch("deploy_workstation.list_environment_images", return_value=listed_images),
            patch("deploy_workstation.print_image_list"),
            patch("deploy_workstation.pick_image_interactively", return_value=selected_image),
            patch("deploy_workstation.deploy_stack") as deploy_stack_mock,
            patch("deploy_workstation.run_post_deploy_check") as post_check_mock,
        ):
            result = main()

        self.assertEqual(0, result)
        deploy_stack_mock.assert_called_once_with(stack_dir="/tmp/gastown", ami_id="ami-b")
        post_check_mock.assert_called_once_with(
            stack_dir="/tmp/gastown",
            stack_name="GastownWorkstationStack",
        )

    def test_resolve_exact_image_id_returns_match(self) -> None:
        """Expected: exact-name AMI lookup returns matched image id."""
        ec2_client = Mock()
        ec2_client.describe_images.return_value = {
            "Images": [
                {
                    "ImageId": "ami-1234",
                    "Name": "gastown_release-a",
                    "CreationDate": "2026-03-01T00:00:00.000Z",
                }
            ]
        }

        result = resolve_exact_image_id(ec2_client, expected_name="gastown_release-a")

        self.assertEqual("ami-1234", result)

    def test_list_environment_images_returns_newest_first(self) -> None:
        """Edge: list mode sorts environment AMIs by creation date descending."""
        ec2_client = Mock()
        ec2_client.describe_images.return_value = {
            "Images": [
                {
                    "ImageId": "ami-older",
                    "Name": "gastown_old",
                    "State": "available",
                    "CreationDate": "2026-02-01T01:00:00.000Z",
                },
                {
                    "ImageId": "ami-newer",
                    "Name": "gastown_new",
                    "State": "pending",
                    "CreationDate": "2026-02-15T01:00:00.000Z",
                },
            ]
        }

        images = list_environment_images(ec2_client, environment="gastown")

        self.assertEqual("ami-newer", images[0]["image_id"])
        self.assertEqual("pending", images[0]["state"])

    def test_resolve_exact_image_id_raises_when_missing(self) -> None:
        """Failure: missing AMI name raises a pre-deploy error."""
        ec2_client = Mock()
        ec2_client.describe_images.return_value = {"Images": []}

        with self.assertRaisesRegex(
            RuntimeError,
            "Requested AMI 'gastown_missing' was not found",
        ):
            resolve_exact_image_id(ec2_client, expected_name="gastown_missing")

    def test_pick_image_interactively_returns_selected_image(self) -> None:
        """Expected: list-and-pick mode returns selected image metadata."""
        output = io.StringIO()
        images = [
            {
                "image_id": "ami-1111",
                "name": "gastown_one",
                "state": "available",
                "creation_date": "2026-02-01T01:00:00.000Z",
            },
            {
                "image_id": "ami-2222",
                "name": "gastown_two",
                "state": "available",
                "creation_date": "2026-02-02T01:00:00.000Z",
            },
        ]

        result = pick_image_interactively(
            images,
            input_func=lambda _: "2",
            out=output,
        )

        self.assertEqual("ami-2222", result["image_id"])

    def test_validate_mode_arguments_rejects_invalid_pick_without_list(self) -> None:
        """Failure: AMI_PICK requires AMI_LIST to avoid ambiguous behavior."""
        with self.assertRaisesRegex(RuntimeError, "AMI_PICK requires AMI_LIST=1."):
            validate_mode_arguments(ami_load_tag="", ami_list=False, ami_pick=True)

    def test_deploy_stack_passes_restored_bootstrap_context_when_enabled(self) -> None:
        """Expected: restored AMI deploy can opt-in bootstrap via CDK context."""
        with patch("deploy_workstation.run_command") as run_command:
            deploy_stack(
                stack_dir="/tmp/stack",
                ami_id="ami-1234",
                bootstrap_on_restored_ami=True,
            )

        args = run_command.call_args.args[0]
        self.assertIn("-c", args)
        self.assertIn("ami_id=ami-1234", args)
        self.assertIn("bootstrap_on_restored_ami=true", args)

    def test_deploy_stack_omits_ami_context_without_ami_id(self) -> None:
        """Edge: default deploy path keeps command free of AMI contexts."""
        with patch("deploy_workstation.run_command") as run_command:
            deploy_stack(
                stack_dir="/tmp/stack",
                ami_id=None,
                bootstrap_on_restored_ami=True,
            )

        args = run_command.call_args.args[0]
        self.assertNotIn("ami_id=ami-1234", args)
        self.assertNotIn("bootstrap_on_restored_ami=true", args)

    def test_build_ami_lookup_error_message_is_actionable(self) -> None:
        """Expected: AMI lookup failures provide next-step guidance."""
        message = build_ami_lookup_error_message("list AMIs for 'gastown'")

        self.assertIn("Unable to list AMIs for 'gastown'", message)
        self.assertIn("ec2:DescribeImages", message)

    def test_list_environment_images_raises_actionable_error_on_describe_failure(self) -> None:
        """Failure: EC2 describe errors in list mode are standardized for users."""
        ec2_client = Mock()
        ec2_client.describe_images.side_effect = Exception("boom")

        with self.assertRaisesRegex(RuntimeError, "Unable to list AMIs for 'gastown'"):
            list_environment_images(ec2_client, environment="gastown")

    def test_resolve_exact_image_id_raises_actionable_error_on_describe_failure(self) -> None:
        """Failure: EC2 describe errors in load mode are standardized for users."""
        ec2_client = Mock()
        ec2_client.describe_images.side_effect = Exception("boom")

        with self.assertRaisesRegex(RuntimeError, "Unable to load AMI 'gastown_release-a'"):
            resolve_exact_image_id(ec2_client, expected_name="gastown_release-a")

    @patch("deploy_workstation.subprocess.run")
    def test_run_command_raises_on_timeout(self, run_mock: Mock) -> None:
        """Failure: command timeout returns a consistent wait/triage error."""
        run_mock.side_effect = subprocess.TimeoutExpired(cmd=["uv", "run"], timeout=5)

        with self.assertRaisesRegex(RuntimeError, "Timed out while waiting"):
            run_command(["uv", "run"], cwd=".", timeout_seconds=5)

    @patch("deploy_workstation.subprocess.run")
    def test_run_command_raises_on_non_zero_exit(self, run_mock: Mock) -> None:
        """Edge: command failure includes command and exit code context."""
        run_mock.side_effect = subprocess.CalledProcessError(
            returncode=2,
            cmd=["uv", "run", "cdk", "deploy"],
        )

        with self.assertRaisesRegex(RuntimeError, "Command failed \\(exit code 2\\)"):
            run_command(["uv", "run", "cdk", "deploy"], cwd=".")

    def test_run_ami_permission_preflight_succeeds_for_describe_images(self) -> None:
        """Expected: preflight passes when describe_images permission is available."""
        ec2_client = Mock()
        ec2_client.describe_images.return_value = {"Images": []}

        run_ami_permission_preflight(ec2_client, environment="gastown")

        ec2_client.describe_images.assert_called_once_with(
            Owners=["self"],
            Filters=[{"Name": "name", "Values": ["gastown_*"]}],
        )

    def test_run_ami_permission_preflight_raises_generic_api_error(self) -> None:
        """Edge: non-IAM EC2 API failures are surfaced with context."""
        ec2_client = Mock()
        ec2_client.describe_images.side_effect = ClientError(
            error_response={"Error": {"Code": "RequestLimitExceeded", "Message": "Too many requests"}},
            operation_name="DescribeImages",
        )

        with self.assertRaisesRegex(RuntimeError, "EC2 API call failed during AMI IAM preflight"):
            run_ami_permission_preflight(ec2_client, environment="gastown")

    def test_run_ami_permission_preflight_reports_missing_permissions(self) -> None:
        """Failure: IAM preflight prints required remediation for AccessDenied."""
        ec2_client = Mock()
        ec2_client.describe_images.side_effect = ClientError(
            error_response={"Error": {"Code": "UnauthorizedOperation", "Message": "Denied"}},
            operation_name="DescribeImages",
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Missing required EC2 image permission\\(s\\): ec2:DescribeImages",
        ):
            run_ami_permission_preflight(ec2_client, environment="gastown")


if __name__ == "__main__":
    unittest.main()
