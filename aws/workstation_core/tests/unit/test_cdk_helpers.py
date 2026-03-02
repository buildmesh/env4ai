"""Unit tests for shared CDK helper functions."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from workstation_core import AmiSelectorConfig, EnvironmentSpec
from workstation_core.cdk_helpers import (
    build_bootstrap_user_data,
    build_spot_fleet_launch_specification,
    resolve_ami_id,
    resolve_subnet_availability_zone,
)


class CdkHelpersTests(unittest.TestCase):
    """Validate shared workstation CDK helper behavior."""

    @staticmethod
    def _environment_spec() -> EnvironmentSpec:
        """Build a minimal valid environment spec for helper tests."""
        return EnvironmentSpec(
            environment_key="gastown",
            display_name="Gastown",
            bootstrap_files=("deps.sh", "build.sh"),
            default_ami_selector=AmiSelectorConfig(
                owner="099720109477",
                name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
                filters={"architecture": ("x86_64",)},
            ),
            instance_type="t3.large",
            volume_size=40,
            spot_price="0.1",
        )

    def test_build_bootstrap_user_data_concatenates_files_in_order(self) -> None:
        """Expected: bootstrap helper concatenates and base64-encodes init scripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            init_dir = Path(tmpdir) / "init"
            init_dir.mkdir()
            (init_dir / "deps.sh").write_text("one\n", encoding="utf-8")
            (init_dir / "build.sh").write_text("two\n", encoding="utf-8")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                encoded = build_bootstrap_user_data(("deps.sh", "build.sh"))
            finally:
                os.chdir(original_cwd)

        self.assertEqual("b25lCnR3bwo=", encoded)

    def test_build_launch_spec_omits_user_data_when_disabled(self) -> None:
        """Edge: launch spec excludes userData when bootstrap is disabled."""
        launch_spec = build_spot_fleet_launch_specification(
            ami_id="ami-12345",
            instance_type="t3.large",
            security_group_id="sg-12345",
            subnet_id="subnet-12345",
            volume_size=100,
            include_bootstrap_user_data=False,
            bootstrap_files=("deps.sh",),
        )

        self.assertEqual("ami-12345", launch_spec["image_id"])
        self.assertNotIn("user_data", launch_spec)

    def test_resolve_ami_id_rejects_invalid_source(self) -> None:
        """Failure: unsupported AMI source values are rejected immediately."""
        with self.assertRaisesRegex(
            ValueError,
            "ami_source must be either 'default' or 'selected'",
        ):
            resolve_ami_id(
                stack=mock.Mock(),
                environment_spec=self._environment_spec(),
                ami_source="invalid",  # type: ignore[arg-type]
            )

    def test_resolve_subnet_availability_zone_rejects_negative_index(self) -> None:
        """Failure: negative AZ index is rejected with a clear error."""
        with self.assertRaisesRegex(
            ValueError,
            "availability_zone_index must be greater than or equal to 0",
        ):
            resolve_subnet_availability_zone(-1)

    def test_resolve_ami_id_uses_lookup_for_default_source(self) -> None:
        """Expected: default source mode resolves AMI ID through CDK lookup."""
        machine_image = mock.Mock()
        machine_image.get_image.return_value = mock.Mock(image_id="ami-default")
        ec2_module = mock.Mock()
        ec2_module.MachineImage.lookup.return_value = machine_image

        with mock.patch(
            "workstation_core.cdk_helpers._require_aws_cdk",
            return_value=(mock.Mock(), ec2_module),
        ):
            ami_id = resolve_ami_id(
                stack=mock.Mock(),
                environment_spec=self._environment_spec(),
                ami_source="default",
            )

        self.assertEqual("ami-default", ami_id)
        ec2_module.MachineImage.lookup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
