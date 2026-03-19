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
