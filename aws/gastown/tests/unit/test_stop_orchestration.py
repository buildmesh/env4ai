import unittest
from unittest.mock import Mock

from workstation_core import StopOrchestrationInputs, parse_stop_ami_config, run_stop_orchestration


class StopOrchestrationTests(unittest.TestCase):
    def test_run_stop_orchestration_destroys_without_save_when_save_disabled(self) -> None:
        """Expected: default stop path destroys stack without AMI save operations."""
        resolve_running_instance = Mock(return_value="i-123")
        create_image = Mock(return_value="ami-123")
        wait_for_image = Mock()
        destroy_stack = Mock()

        saved_image_id = run_stop_orchestration(
            StopOrchestrationInputs(
                environment_key="gastown",
                stack_name="GastownWorkstationStack",
                spot_fleet_logical_id="GastownSpotFleet",
                ami_save=False,
                ami_tag=None,
            ),
            resolve_running_instance_id=resolve_running_instance,
            create_image=create_image,
            wait_for_image_available=wait_for_image,
            destroy_stack=destroy_stack,
        )

        self.assertIsNone(saved_image_id)
        resolve_running_instance.assert_not_called()
        create_image.assert_not_called()
        wait_for_image.assert_not_called()
        destroy_stack.assert_called_once_with()

    def test_run_stop_orchestration_saves_and_destroys_when_save_enabled(self) -> None:
        """Edge: save-on-stop uses deterministic AMI naming and then destroys stack."""
        calls: list[str] = []

        def resolve_running_instance_id() -> str:
            calls.append("resolve")
            return "i-abc"

        def create_image(instance_id: str, image_name: str) -> str:
            calls.append(f"create:{instance_id}:{image_name}")
            return "ami-new"

        def wait_for_image_available(image_id: str) -> None:
            calls.append(f"wait:{image_id}")

        def destroy_stack() -> None:
            calls.append("destroy")

        saved_image_id = run_stop_orchestration(
            StopOrchestrationInputs(
                environment_key="gastown",
                stack_name="GastownWorkstationStack",
                spot_fleet_logical_id="GastownSpotFleet",
                ami_save=True,
                ami_tag=" 20260302 ",
            ),
            resolve_running_instance_id=resolve_running_instance_id,
            create_image=create_image,
            wait_for_image_available=wait_for_image_available,
            destroy_stack=destroy_stack,
        )

        self.assertEqual("ami-new", saved_image_id)
        self.assertEqual(
            [
                "resolve",
                "create:i-abc:gastown_20260302",
                "wait:ami-new",
                "destroy",
            ],
            calls,
        )

    def test_run_stop_orchestration_aborts_destroy_when_save_fails(self) -> None:
        """Failure: destroy is blocked when save-on-stop fails."""
        destroy_stack = Mock()
        with self.assertRaisesRegex(RuntimeError, "wait failed"):
            run_stop_orchestration(
                StopOrchestrationInputs(
                    environment_key="gastown",
                    stack_name="GastownWorkstationStack",
                    spot_fleet_logical_id="GastownSpotFleet",
                    ami_save=True,
                    ami_tag="20260302",
                ),
                resolve_running_instance_id=lambda: "i-abc",
                create_image=lambda _instance_id, _image_name: "ami-fail",
                wait_for_image_available=lambda _image_id: (_ for _ in ()).throw(
                    RuntimeError("wait failed")
                ),
                destroy_stack=destroy_stack,
            )

        destroy_stack.assert_not_called()

    def test_parse_stop_ami_config_requires_tag_when_save_enabled(self) -> None:
        """Failure: save flag without AMI tag is rejected."""
        with self.assertRaisesRegex(RuntimeError, "AMI_SAVE=1 requires AMI_TAG"):
            parse_stop_ami_config({"AMI_SAVE": "1"})


if __name__ == "__main__":
    unittest.main()
