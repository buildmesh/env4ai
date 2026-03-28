"""Unit tests for the shared WorkstationStack CDK construct.

Previously duplicated across builder/ and gastown/; now consolidated here
because the stack implementation is identical for all environments.
"""

from pathlib import Path
import sys
import unittest

_BASE_STACK = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
# environment_config must be importable before workstation_stack is imported.
sys.path.insert(0, str(_FIXTURES))
sys.path.insert(0, str(_BASE_STACK))

import aws_cdk as core
import aws_cdk.assertions as assertions
from aws_cdk.assertions import Match

from workstation.workstation_stack import WorkstationStack
from workstation.env4ai_network_stack import Env4aiNetworkStack
from workstation_core import AmiSelectorConfig, EnvironmentSpec
from workstation_core.cdk_helpers import resolve_ami_id, resolve_subnet_availability_zone

# A deterministic spec so resource logical IDs are predictable in assertions.
TEST_SPEC = EnvironmentSpec(
    environment_key="test",
    display_name="Test",
    bootstrap_files=("bootstrap.sh",),
    default_ami_selector=AmiSelectorConfig(
        owner="099720109477",
        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
        filters={"architecture": ("x86_64",)},
    ),
    subnet_cidr="10.0.99.0/24",
    instance_type="t3.micro",
    volume_size=8,
    spot_price="0.05",
)
# spot_fleet_logical_id == "TestSpotFleet" with display_name="Test"


class WorkstationStackTests(unittest.TestCase):
    @staticmethod
    def _test_env() -> core.Environment:
        """Return a deterministic CDK env for stack synthesis in tests."""
        return core.Environment(account="111111111111", region="us-west-2")

    def _make_stack(
        self,
        app: core.App,
        stack_id: str,
        **kwargs,
    ) -> WorkstationStack:
        """Create a workstation stack connected to the shared network stack."""
        network_stack = Env4aiNetworkStack(app, f"{stack_id}-network", env=self._test_env())
        return WorkstationStack(
            app,
            stack_id,
            shared_vpc=network_stack.vpc,
            shared_igw_id=network_stack.internet_gateway.ref,
            environment_spec=TEST_SPEC,
            env=self._test_env(),
            **kwargs,
        )

    def test_subnet_az_uses_dynamic_get_azs_select_by_default(self) -> None:
        """Expected: default subnet AZ is dynamic from deployment region."""
        app = core.App()
        stack = self._make_stack(app, "aws-workstation-default-az")
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
        stack = self._make_stack(
            app,
            "aws-workstation-secondary-az",
            availability_zone_index=1,
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
        stack = self._make_stack(
            app,
            "aws-workstation-ami-override",
            ami_id_override="ami-override123",
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

    def test_selected_ami_defaults_to_skipping_bootstrap_user_data(self) -> None:
        """Expected: selected AMI path omits user data unless explicitly enabled."""
        app = core.App()
        stack = self._make_stack(
            app,
            "aws-workstation-selected-ami-no-bootstrap",
            ami_source="selected",
            selected_ami_id="ami-0123456789abcdef0",
        )
        template = assertions.Template.from_stack(stack)

        template.has_resource_properties(
            "AWS::EC2::SpotFleet",
            {
                "SpotFleetRequestConfigData": {
                    "LaunchSpecifications": assertions.Match.array_with(
                        [
                            assertions.Match.object_like(
                                {
                                    "ImageId": "ami-0123456789abcdef0",
                                    "UserData": assertions.Match.absent(),
                                }
                            )
                        ]
                    )
                }
            },
        )

    def test_selected_ami_allows_explicit_bootstrap_opt_in(self) -> None:
        """Edge: selected AMI path can opt in to full bootstrap user data."""
        app = core.App()
        stack = self._make_stack(
            app,
            "aws-workstation-selected-ami-bootstrap-opt-in",
            ami_source="selected",
            selected_ami_id="ami-0123456789abcdef0",
            bootstrap_on_restored_ami=True,
        )
        template = assertions.Template.from_stack(stack)

        template.has_resource_properties(
            "AWS::EC2::SpotFleet",
            {
                "SpotFleetRequestConfigData": {
                    "LaunchSpecifications": assertions.Match.array_with(
                        [
                            assertions.Match.object_like(
                                {
                                    "ImageId": "ami-0123456789abcdef0",
                                    "UserData": assertions.Match.any_value(),
                                }
                            )
                        ]
                    )
                }
            },
        )

    def test_ami_override_conflicts_with_selected_ami_id(self) -> None:
        """Failure: conflicting AMI override values are rejected."""
        app = core.App()
        with self.assertRaisesRegex(
            ValueError,
            "ami_id_override conflicts with selected_ami_id",
        ):
            WorkstationStack(
                app,
                "aws-workstation-conflicting-ami-overrides",
                shared_vpc=Env4aiNetworkStack(app, "conflict-network", env=self._test_env()).vpc,
                shared_igw_id="igw-12345678",
                ami_id_override="ami-override123",
                ami_source="selected",
                selected_ami_id="ami-different456",
                environment_spec=TEST_SPEC,
                env=self._test_env(),
            )

    def test_selected_ami_requires_explicit_ami_id(self) -> None:
        """Failure: selected source mode must provide a concrete AMI ID."""
        app = core.App()
        with self.assertRaisesRegex(
            ValueError,
            "selected_ami_id is required when ami_source is 'selected'",
        ):
            WorkstationStack(
                app,
                "aws-workstation-selected-ami-missing-id",
                shared_vpc=Env4aiNetworkStack(app, "missing-network", env=self._test_env()).vpc,
                shared_igw_id="igw-12345678",
                ami_source="selected",
                environment_spec=TEST_SPEC,
                env=self._test_env(),
            )

    def test_resolve_ami_id_rejects_unknown_source(self) -> None:
        """Failure: invalid AMI source values are rejected."""
        app = core.App()
        stack = core.Stack(app, "ami-id-resolver-stack", env=self._test_env())

        with self.assertRaisesRegex(
            ValueError,
            "ami_source must be either 'default' or 'selected'",
        ):
            resolve_ami_id(
                stack=stack,
                environment_spec=TEST_SPEC,
                ami_source="restored",  # type: ignore[arg-type]
            )

    def test_default_ami_path_includes_bootstrap_userdata(self) -> None:
        """Expected: default Ubuntu path includes full bootstrap user data."""
        app = core.App()
        stack = self._make_stack(app, "aws-workstation-default-bootstrap")
        template_dict = assertions.Template.from_stack(stack).to_json()
        launch_spec = template_dict["Resources"]["TestSpotFleet"]["Properties"][
            "SpotFleetRequestConfigData"
        ]["LaunchSpecifications"][0]

        self.assertIn("UserData", launch_spec)
        self.assertTrue(str(launch_spec["UserData"]).strip())

    def test_restored_ami_path_skips_bootstrap_userdata_by_default(self) -> None:
        """Edge: restored-AMI deploy omits bootstrap user data unless explicitly requested."""
        app = core.App()
        stack = self._make_stack(
            app,
            "aws-workstation-restored-no-bootstrap",
            ami_id_override="ami-restored001",
        )
        template_dict = assertions.Template.from_stack(stack).to_json()
        launch_spec = template_dict["Resources"]["TestSpotFleet"]["Properties"][
            "SpotFleetRequestConfigData"
        ]["LaunchSpecifications"][0]

        self.assertNotIn("UserData", launch_spec)

    def test_restored_ami_path_allows_explicit_bootstrap_override(self) -> None:
        """Expected: restored-AMI deploy can opt-in to bootstrap user data."""
        app = core.App()
        stack = self._make_stack(
            app,
            "aws-workstation-restored-with-bootstrap",
            ami_id_override="ami-restored002",
            bootstrap_on_restored_ami=True,
        )
        template_dict = assertions.Template.from_stack(stack).to_json()
        launch_spec = template_dict["Resources"]["TestSpotFleet"]["Properties"][
            "SpotFleetRequestConfigData"
        ]["LaunchSpecifications"][0]

        self.assertIn("UserData", launch_spec)

    def test_stack_uses_shared_network_resources_instead_of_creating_vpc_and_igw(self) -> None:
        """Expected: environment stacks only create tenant resources inside the shared VPC."""
        app = core.App()
        stack = self._make_stack(app, "aws-workstation-shared-network")
        template = assertions.Template.from_stack(stack)
        template_json = template.to_json()

        self.assertNotIn(
            "AWS::EC2::VPC",
            {
                resource["Type"]
                for resource in template_json["Resources"].values()
            },
        )
        self.assertNotIn(
            "AWS::EC2::InternetGateway",
            {
                resource["Type"]
                for resource in template_json["Resources"].values()
            },
        )
        template.has_resource_properties(
            "AWS::EC2::Subnet",
            {"CidrBlock": TEST_SPEC.subnet_cidr},
        )


if __name__ == "__main__":
    unittest.main()
