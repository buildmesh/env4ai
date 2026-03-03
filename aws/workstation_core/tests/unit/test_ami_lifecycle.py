"""Unit tests for shared AMI lifecycle helpers."""

from __future__ import annotations

import io
import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError

from workstation_core.ami_lifecycle import (
    AmiModeConfig,
    pick_image_interactively,
    print_image_list,
    resolve_ami_selection,
    run_ami_permission_preflight,
    validate_mode_arguments,
)


class AmiLifecycleTests(unittest.TestCase):
    """Validate AMI lifecycle selection and IAM guard behavior."""

    def test_resolve_ami_selection_load_mode_returns_exact_ami_id(self) -> None:
        """Expected: AMI_LOAD resolves exact AMI and proceeds with deploy."""
        ec2_client = Mock()
        ec2_client.describe_images.side_effect = [
            {"Images": []},
            {"Images": [{"ImageId": "ami-load", "Name": "gastown_20260301"}]},
        ]
        output = io.StringIO()

        result = resolve_ami_selection(
            ec2_client=ec2_client,
            environment_key="gastown",
            mode=AmiModeConfig(
                ami_load_tag="20260301",
                ami_list=False,
                ami_pick=False,
                ami_bootstrap=False,
            ),
            out=output,
        )

        self.assertTrue(result.should_deploy)
        self.assertEqual("ami-load", result.selected_ami_id)
        self.assertIn("Resolved AMI gastown_20260301 -> ami-load", output.getvalue())

    def test_resolve_ami_selection_list_mode_without_pick_lists_and_exits(self) -> None:
        """Edge: list-only mode prints AMIs and exits without running deploy."""
        ec2_client = Mock()
        ec2_client.describe_images.side_effect = [
            {"Images": []},
            {
                "Images": [
                    {
                        "ImageId": "ami-list",
                        "Name": "gastown_saved",
                        "State": "available",
                        "CreationDate": "2026-02-20T00:00:00.000Z",
                    }
                ]
            },
        ]
        output = io.StringIO()

        result = resolve_ami_selection(
            ec2_client=ec2_client,
            environment_key="gastown",
            mode=AmiModeConfig(
                ami_load_tag="",
                ami_list=True,
                ami_pick=False,
                ami_bootstrap=False,
            ),
            out=output,
        )

        self.assertFalse(result.should_deploy)
        self.assertIsNone(result.selected_ami_id)
        self.assertIn("Available AMIs:", output.getvalue())
        self.assertIn("created=2026-02-20T00:00:00.000Z", output.getvalue())
        self.assertNotIn("ami-list", output.getvalue())

    def test_print_image_list_marks_pending_or_failed_as_disabled(self) -> None:
        """Expected: pending/failed AMIs are visible but clearly marked non-deployable."""
        output = io.StringIO()
        print_image_list(
            [
                {
                    "name": "gastown_pending",
                    "image_id": "ami-pending",
                    "state": "pending",
                    "creation_date": "2026-03-01T00:00:00.000Z",
                },
                {
                    "name": "gastown_failed",
                    "image_id": "ami-failed",
                    "state": "failed",
                    "creation_date": "2026-02-28T00:00:00.000Z",
                },
            ],
            out=output,
        )
        rendered = output.getvalue()
        self.assertIn("[disabled: state=pending]", rendered)
        self.assertIn("[disabled: state=failed]", rendered)

    def test_pick_image_interactively_rejects_non_deployable_and_reprompts(self) -> None:
        """Failure: selecting pending/failed AMI does not return until available is chosen."""
        output = io.StringIO()
        images = [
            {
                "name": "gastown_pending",
                "image_id": "ami-pending",
                "state": "pending",
                "creation_date": "2026-03-01T00:00:00.000Z",
            },
            {
                "name": "gastown_ready",
                "image_id": "ami-ready",
                "state": "available",
                "creation_date": "2026-02-20T00:00:00.000Z",
            },
        ]
        inputs = iter(["1", "2"])

        selected = pick_image_interactively(
            images,
            input_func=lambda _prompt: next(inputs),
            out=output,
        )

        self.assertEqual("ami-ready", selected["image_id"])
        self.assertIn("not deployable", output.getvalue())

    def test_resolve_ami_selection_pick_mode_requires_detail_confirmation(self) -> None:
        """Expected: available AMI selection renders detail view and needs yes confirmation."""
        ec2_client = Mock()
        ec2_client.describe_images.side_effect = [
            {"Images": []},
            {
                "Images": [
                    {
                        "ImageId": "ami-ready",
                        "Name": "gastown_saved",
                        "ImageArn": "arn:aws:ec2:us-west-2:123456789012:image/ami-ready",
                        "State": "available",
                        "CreationDate": "2026-02-20T00:00:00.000Z",
                    }
                ]
            },
        ]
        output = io.StringIO()
        inputs = iter(["1", "yes"])

        result = resolve_ami_selection(
            ec2_client=ec2_client,
            environment_key="gastown",
            mode=AmiModeConfig(
                ami_load_tag="",
                ami_list=True,
                ami_pick=True,
                ami_bootstrap=False,
            ),
            input_func=lambda _prompt: next(inputs),
            out=output,
        )

        self.assertTrue(result.should_deploy)
        self.assertEqual("ami-ready", result.selected_ami_id)
        rendered = output.getvalue()
        self.assertIn("Selected AMI details:", rendered)
        self.assertIn("arn: arn:aws:ec2", rendered.lower())

    def test_resolve_ami_selection_pick_cancel_confirmation_exits_without_deploy(self) -> None:
        """Edge: non-yes confirmation cancels deploy with no selected AMI."""
        ec2_client = Mock()
        ec2_client.describe_images.side_effect = [
            {"Images": []},
            {
                "Images": [
                    {
                        "ImageId": "ami-ready",
                        "Name": "gastown_saved",
                        "State": "available",
                        "CreationDate": "2026-02-20T00:00:00.000Z",
                    }
                ]
            },
        ]
        output = io.StringIO()
        inputs = iter(["1", "no"])

        result = resolve_ami_selection(
            ec2_client=ec2_client,
            environment_key="gastown",
            mode=AmiModeConfig(
                ami_load_tag="",
                ami_list=True,
                ami_pick=True,
                ami_bootstrap=False,
            ),
            input_func=lambda _prompt: next(inputs),
            out=output,
        )

        self.assertFalse(result.should_deploy)
        self.assertIsNone(result.selected_ami_id)
        self.assertIn("AMI deploy canceled.", output.getvalue())

    def test_validate_mode_arguments_rejects_invalid_pick_without_list(self) -> None:
        """Failure: AMI_PICK without AMI_LIST is rejected with actionable guidance."""
        with self.assertRaisesRegex(RuntimeError, "AMI_PICK requires AMI_LIST=1."):
            validate_mode_arguments(ami_load_tag="", ami_list=False, ami_pick=True)

    def test_run_ami_permission_preflight_reports_missing_permissions(self) -> None:
        """Failure: IAM preflight exposes required permission names on denial."""
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
