"""Unit tests for the shared Env4ai network CDK stack."""

from pathlib import Path
import sys
import unittest

import aws_cdk as core
import aws_cdk.assertions as assertions

_BASE_STACK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE_STACK))

from workstation.env4ai_network_stack import Env4aiNetworkStack


class Env4aiNetworkStackTests(unittest.TestCase):
    """Validate the dedicated shared network stack shape."""

    @staticmethod
    def _test_env() -> core.Environment:
        """Return a deterministic CDK env for stack synthesis in tests."""
        return core.Environment(account="111111111111", region="us-west-2")

    def test_network_stack_synthesizes_one_vpc_and_one_igw(self) -> None:
        """Expected: the shared network stack owns exactly one VPC and one IGW."""
        app = core.App()
        stack = Env4aiNetworkStack(app, "Env4aiNetworkStack", env=self._test_env())
        template = assertions.Template.from_stack(stack)

        template.resource_count_is("AWS::EC2::VPC", 1)
        template.resource_count_is("AWS::EC2::InternetGateway", 1)
        template.resource_count_is("AWS::EC2::VPCGatewayAttachment", 1)
        template.has_resource_properties(
            "AWS::EC2::VPC",
            {
                "CidrBlock": "10.0.0.0/16",
                "Tags": assertions.Match.array_with(
                    [{"Key": "Name", "Value": "env4ai"}]
                ),
            },
        )

    def test_network_stack_exposes_shared_resource_outputs(self) -> None:
        """Edge: operators can inspect the shared VPC, IGW, and CIDR via outputs."""
        app = core.App()
        stack = Env4aiNetworkStack(app, "Env4aiNetworkStack", env=self._test_env())
        template = assertions.Template.from_stack(stack)
        outputs = template.to_json()["Outputs"]

        self.assertIn("VpcId", outputs)
        self.assertIn("InternetGatewayId", outputs)
        self.assertIn("VpcCidr", outputs)


if __name__ == "__main__":
    unittest.main()
