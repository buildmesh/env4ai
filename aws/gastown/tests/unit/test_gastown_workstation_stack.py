import unittest

import aws_cdk as core
import aws_cdk.assertions as assertions
from aws_cdk.assertions import Match

from gastown_workstation.gastown_workstation_stack import (
    GastownWorkstationStack,
    resolve_subnet_availability_zone,
)


class GastownWorkstationStackTests(unittest.TestCase):
    @staticmethod
    def _test_env() -> core.Environment:
        """Return a deterministic CDK env for stack synthesis in tests."""
        return core.Environment(account="111111111111", region="us-west-2")

    def test_subnet_az_uses_dynamic_get_azs_select_by_default(self) -> None:
        """Expected: default subnet AZ is dynamic from deployment region."""
        app = core.App()
        stack = GastownWorkstationStack(
            app, "aws-workstation-default-az", env=self._test_env()
        )
        template = assertions.Template.from_stack(stack)

        template.has_resource_properties(
            "AWS::EC2::Subnet",
            {
                "AvailabilityZone": {
                    "Fn::Select": [
                        0,
                        {"Fn::GetAZs": ""},
                    ]
                }
            },
        )

    def test_subnet_az_allows_non_default_index(self) -> None:
        """Edge: stack supports selecting a non-default AZ index."""
        app = core.App()
        stack = GastownWorkstationStack(
            app,
            "aws-workstation-secondary-az",
            availability_zone_index=1,
            env=self._test_env(),
        )
        template = assertions.Template.from_stack(stack)

        template.has_resource_properties(
            "AWS::EC2::Subnet",
            {
                "AvailabilityZone": {
                    "Fn::Select": [
                        1,
                        {"Fn::GetAZs": ""},
                    ]
                }
            },
        )

    def test_resolve_subnet_availability_zone_raises_on_negative_index(self) -> None:
        """Failure: negative AZ index is rejected with a clear error."""
        with self.assertRaisesRegex(
            ValueError,
            "availability_zone_index must be greater than or equal to 0",
        ):
            resolve_subnet_availability_zone(-1)

    def test_stack_uses_ami_override_when_context_provided(self) -> None:
        """Expected: Spot Fleet launch spec uses explicit deploy-time AMI override."""
        app = core.App()
        stack = GastownWorkstationStack(
            app,
            "aws-workstation-ami-override",
            ami_id_override="ami-override123",
            env=self._test_env(),
        )
        template = assertions.Template.from_stack(stack)

        template.has_resource_properties(
            "AWS::EC2::SpotFleet",
            {
                "SpotFleetRequestConfigData": {
                    "LaunchSpecifications": Match.array_with(
                        [Match.object_like({"ImageId": "ami-override123"})]
                    )
                }
            },
        )

    def test_default_ami_path_includes_bootstrap_userdata(self) -> None:
        """Expected: default Ubuntu path includes full bootstrap user data."""
        app = core.App()
        stack = GastownWorkstationStack(
            app, "aws-workstation-default-bootstrap", env=self._test_env()
        )
        template_dict = assertions.Template.from_stack(stack).to_json()
        launch_spec = template_dict["Resources"]["GastownSpotFleet"]["Properties"][
            "SpotFleetRequestConfigData"
        ]["LaunchSpecifications"][0]

        self.assertIn("UserData", launch_spec)
        self.assertTrue(str(launch_spec["UserData"]).strip())

    def test_restored_ami_path_skips_bootstrap_userdata_by_default(self) -> None:
        """Edge: restored-AMI deploy omits bootstrap user data unless explicitly requested."""
        app = core.App()
        stack = GastownWorkstationStack(
            app,
            "aws-workstation-restored-no-bootstrap",
            ami_id_override="ami-restored001",
            env=self._test_env(),
        )
        template_dict = assertions.Template.from_stack(stack).to_json()
        launch_spec = template_dict["Resources"]["GastownSpotFleet"]["Properties"][
            "SpotFleetRequestConfigData"
        ]["LaunchSpecifications"][0]

        self.assertNotIn("UserData", launch_spec)

    def test_restored_ami_path_allows_explicit_bootstrap_override(self) -> None:
        """Expected: restored-AMI deploy can opt-in to bootstrap user data."""
        app = core.App()
        stack = GastownWorkstationStack(
            app,
            "aws-workstation-restored-with-bootstrap",
            ami_id_override="ami-restored002",
            bootstrap_on_restored_ami=True,
            env=self._test_env(),
        )
        template_dict = assertions.Template.from_stack(stack).to_json()
        launch_spec = template_dict["Resources"]["GastownSpotFleet"]["Properties"][
            "SpotFleetRequestConfigData"
        ]["LaunchSpecifications"][0]

        self.assertIn("UserData", launch_spec)


if __name__ == "__main__":
    unittest.main()
