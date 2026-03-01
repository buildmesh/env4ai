import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from deploy_workstation import (  # noqa: E402
    deploy_stack,
    list_environment_images,
    pick_image_interactively,
    resolve_exact_image_id,
    validate_mode_arguments,
)


class DeployWorkstationScriptTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
