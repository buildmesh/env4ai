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


if __name__ == "__main__":
    unittest.main()
