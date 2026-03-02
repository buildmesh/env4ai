from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from deploy_workstation import main  # noqa: E402


class DeployWorkstationScriptTests(unittest.TestCase):
    @staticmethod
    def _args() -> object:
        """Build common argument payload used by builder deploy tests."""
        return type(
            "Args",
            (),
            {
                "environment": "builder",
                "stack_dir": "/tmp/builder",
                "stack_name": "BuilderWorkstationStack",
                "profile": None,
                "region": None,
            },
        )()

    def test_main_deploys_default_path_when_no_ami_controls(self) -> None:
        """Expected: baseline builder deploy path runs without AMI overrides."""
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
        deploy_stack_mock.assert_called_once_with(
            stack_dir="/tmp/builder",
            ami_id=None,
            bootstrap_on_restored_ami=False,
        )
        post_check_mock.assert_called_once_with(
            stack_dir="/tmp/builder",
            stack_name="BuilderWorkstationStack",
        )

    def test_main_deploys_selected_image_when_list_and_pick_enabled(self) -> None:
        """Edge: AMI_LIST+AMI_PICK deploys the selected builder image."""
        ec2_client = Mock()
        listed_images = [
            {
                "image_id": "ami-a",
                "name": "builder_a",
                "state": "available",
                "creation_date": "2026-02-15T00:00:00.000Z",
            },
            {
                "image_id": "ami-b",
                "name": "builder_b",
                "state": "available",
                "creation_date": "2026-02-16T00:00:00.000Z",
            },
        ]
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
            patch("deploy_workstation.pick_image_interactively", return_value=listed_images[1]),
            patch("deploy_workstation.deploy_stack") as deploy_stack_mock,
            patch("deploy_workstation.run_post_deploy_check") as post_check_mock,
        ):
            result = main()

        self.assertEqual(0, result)
        deploy_stack_mock.assert_called_once_with(
            stack_dir="/tmp/builder",
            ami_id="ami-b",
            bootstrap_on_restored_ami=False,
        )
        post_check_mock.assert_called_once_with(
            stack_dir="/tmp/builder",
            stack_name="BuilderWorkstationStack",
        )

    def test_main_raises_when_ami_load_tag_does_not_exist(self) -> None:
        """Failure: AMI_LOAD aborts builder deploy when exact AMI lookup fails."""
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
                side_effect=RuntimeError("Requested AMI 'builder_missing' was not found."),
            ),
            patch("deploy_workstation.deploy_stack") as deploy_stack_mock,
        ):
            with self.assertRaisesRegex(RuntimeError, "Requested AMI 'builder_missing' was not found."):
                main()

        deploy_stack_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
