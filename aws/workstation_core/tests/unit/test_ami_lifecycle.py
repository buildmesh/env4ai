"""Unit tests for shared AMI lifecycle helpers."""

from __future__ import annotations

import io
import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError

from workstation_core.ami_lifecycle import (
    AmiModeConfig,
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
