from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from stop_workstation import main  # noqa: E402


class StopWorkstationScriptTests(unittest.TestCase):
    @staticmethod
    def _args() -> object:
        return type(
            "Args",
            (),
            {
                "environment": "gastown",
                "stack_dir": "/tmp/gastown",
                "stack_name": "GastownWorkstationStack",
                "spot_fleet_logical_id": None,
                "profile": None,
                "region": None,
                "destroy_eip": False,
            },
        )()

    def test_main_destroys_without_save_when_save_flag_is_unset(self) -> None:
        """Expected: wrapper delegates default stop flow without save-on-stop."""
        session = Mock()
        session.region_name = "us-west-2"
        session.client.side_effect = [Mock(), Mock()]

        with (
            patch("stop_workstation.parse_args", return_value=self._args()),
            patch("stop_workstation.parse_stop_ami_config", return_value=(False, None)),
            patch("stop_workstation.boto3.Session", return_value=session),
            patch("stop_workstation.run_stop_orchestration", return_value=None) as run_orchestration,
        ):
            result = main()

        self.assertEqual(0, result)
        run_orchestration.assert_called_once()

    def test_main_passes_ami_save_inputs_when_enabled(self) -> None:
        """Edge: wrapper forwards AMI save options to shared orchestration inputs."""
        session = Mock()
        session.region_name = "us-west-2"
        session.client.side_effect = [Mock(), Mock()]
        with (
            patch("stop_workstation.parse_args", return_value=self._args()),
            patch("stop_workstation.parse_stop_ami_config", return_value=(True, "release-a")),
            patch("stop_workstation.boto3.Session", return_value=session),
            patch("stop_workstation.run_stop_orchestration", return_value="ami-1") as run_orchestration,
            patch("builtins.print"),
        ):
            result = main()

        self.assertEqual(0, result)
        inputs = run_orchestration.call_args.args[0]
        self.assertTrue(inputs.ami_save)
        self.assertEqual("release-a", inputs.ami_tag)
        self.assertEqual("gastown", inputs.environment_key)

    def test_main_passes_release_eip_callback_when_destroy_eip_flag_set(self) -> None:
        """Expected: destroy-eip flag causes a release_eip callback to be passed to orchestration."""
        args = type(
            "Args",
            (),
            {
                "environment": "gastown",
                "stack_dir": "/tmp/gastown",
                "stack_name": "GastownWorkstationStack",
                "spot_fleet_logical_id": None,
                "profile": None,
                "region": None,
                "destroy_eip": True,
            },
        )()
        session = Mock()
        session.region_name = "us-west-2"
        session.client.side_effect = [Mock(), Mock()]
        eip_info = {"allocation_id": "eipalloc-abc123", "public_ip": "1.2.3.4"}

        with (
            patch("stop_workstation.parse_args", return_value=args),
            patch("stop_workstation.parse_stop_ami_config", return_value=(False, None)),
            patch("stop_workstation.boto3.Session", return_value=session),
            patch("stop_workstation.find_eip_by_name", return_value=eip_info),
            patch("stop_workstation.run_stop_orchestration", return_value=None) as run_orchestration,
        ):
            result = main()

        self.assertEqual(0, result)
        call_kwargs = run_orchestration.call_args.kwargs
        self.assertIsNotNone(call_kwargs.get("release_eip"))

    def test_main_warns_and_skips_eip_release_when_no_eip_found(self) -> None:
        """Edge: destroy-eip with no matching EIP logs a warning and passes no callback."""
        args = type(
            "Args",
            (),
            {
                "environment": "gastown",
                "stack_dir": "/tmp/gastown",
                "stack_name": "GastownWorkstationStack",
                "spot_fleet_logical_id": None,
                "profile": None,
                "region": None,
                "destroy_eip": True,
            },
        )()
        session = Mock()
        session.region_name = "us-west-2"
        session.client.side_effect = [Mock(), Mock()]

        with (
            patch("stop_workstation.parse_args", return_value=args),
            patch("stop_workstation.parse_stop_ami_config", return_value=(False, None)),
            patch("stop_workstation.boto3.Session", return_value=session),
            patch("stop_workstation.find_eip_by_name", return_value=None),
            patch("stop_workstation.run_stop_orchestration", return_value=None) as run_orchestration,
            patch("builtins.print"),
        ):
            result = main()

        self.assertEqual(0, result)
        call_kwargs = run_orchestration.call_args.kwargs
        self.assertIsNone(call_kwargs.get("release_eip"))

    def test_main_raises_when_region_is_unresolvable(self) -> None:
        """Failure: wrapper aborts before orchestration if region cannot be resolved."""
        session = Mock()
        session.region_name = None

        with (
            patch("stop_workstation.parse_args", return_value=self._args()),
            patch("stop_workstation.parse_stop_ami_config", return_value=(False, None)),
            patch("stop_workstation.boto3.Session", return_value=session),
        ):
            with self.assertRaisesRegex(RuntimeError, "Unable to resolve AWS region"):
                main()


if __name__ == "__main__":
    unittest.main()
