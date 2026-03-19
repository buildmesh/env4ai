"""Unit tests for save_workstation_ami wrapper script."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from save_workstation_ami import main  # noqa: E402


class SaveWorkstationAmiScriptTests(unittest.TestCase):
    """Validate save-only AMI wrapper behavior."""

    @staticmethod
    def _argv() -> list[str]:
        """Return common args for save-only tests."""
        return [
            "--environment",
            "gastown",
            "--stack-dir",
            "/tmp/gastown",
            "--stack-name",
            "GastownWorkstationStack",
            "--ami-tag",
            "release-a",
        ]

    def test_main_saves_ami_successfully(self) -> None:
        """Expected: wrapper resolves running instance and saves an AMI."""
        session = Mock(region_name="us-west-2")
        ec2_client = Mock()
        cloudformation_client = Mock()
        session.client.side_effect = [ec2_client, cloudformation_client]
        with (
            patch("save_workstation_ami.boto3.Session", return_value=session),
            patch("save_workstation_ami.resolve_running_instance_id", return_value="i-123"),
            patch("save_workstation_ami.create_image_from_instance", return_value="ami-123"),
            patch("save_workstation_ami.wait_for_image_available") as wait_for_image_available,
            patch("save_workstation_ami.load_environment_spec", return_value=None),
            patch("save_workstation_ami._resolve_spot_fleet_logical_id", return_value="GastownSpotFleet"),
        ):
            result = main(self._argv())

        self.assertEqual(0, result)
        wait_for_image_available.assert_called_once_with(ec2_client, image_id="ami-123")

    def test_main_uses_environment_spec_key_when_available(self) -> None:
        """Edge: canonical environment key from spec is used in AMI naming."""
        session = Mock(region_name="us-west-2")
        ec2_client = Mock()
        cloudformation_client = Mock()
        session.client.side_effect = [ec2_client, cloudformation_client]
        environment_spec = Mock(environment_key="canonical-key")
        with (
            patch("save_workstation_ami.boto3.Session", return_value=session),
            patch("save_workstation_ami.resolve_running_instance_id", return_value="i-123"),
            patch("save_workstation_ami.create_image_from_instance", return_value="ami-123") as create_image,
            patch("save_workstation_ami.wait_for_image_available"),
            patch("save_workstation_ami.load_environment_spec", return_value=environment_spec),
            patch("save_workstation_ami._resolve_spot_fleet_logical_id", return_value="GastownSpotFleet"),
        ):
            main(self._argv())

        create_image.assert_called_once_with(
            ec2_client,
            instance_id="i-123",
            image_name="canonical-key_release-a",
        )

    def test_main_raises_when_region_is_unresolvable(self) -> None:
        """Failure: wrapper aborts before save when region cannot be resolved."""
        session = Mock(region_name=None)
        with patch("save_workstation_ami.boto3.Session", return_value=session):
            with self.assertRaisesRegex(RuntimeError, "Unable to resolve AWS region"):
                main(self._argv())


if __name__ == "__main__":
    unittest.main()
