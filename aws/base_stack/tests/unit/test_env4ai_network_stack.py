"""Unit tests for the shared Env4ai network CDK stack."""

from pathlib import Path
import sys
import unittest

import aws_cdk as core
import aws_cdk.assertions as assertions

_BASE_STACK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE_STACK))

from workstation.env4ai_network_stack import Env4aiNetworkStack
from workstation_core.config import get_shared_network_export_name


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
        template.resource_count_is("AWS::EC2::Subnet", 1)
        template.has_resource_properties(
            "AWS::EC2::VPC",
            {
                "CidrBlock": "10.0.0.0/16",
                "Tags": assertions.Match.array_with(
                    [{"Key": "Name", "Value": "env4ai"}]
                ),
            },
        )

    def test_network_stack_creates_shared_ssm_infrastructure(self) -> None:
        """Expected: shared SSM subnet, endpoints, SGs, role, and profile exist."""
        app = core.App()
        stack = Env4aiNetworkStack(app, "Env4aiNetworkStack", env=self._test_env())
        template = assertions.Template.from_stack(stack)

        template.resource_count_is("AWS::EC2::VPCEndpoint", 3)
        template.resource_count_is("AWS::EC2::SecurityGroup", 2)
        template.resource_count_is("AWS::IAM::Role", 1)
        template.resource_count_is("AWS::IAM::InstanceProfile", 1)
        template.has_resource_properties(
            "AWS::EC2::Subnet",
            {
                "CidrBlock": "10.0.250.0/24",
            },
        )
        template.has_resource_properties(
            "AWS::IAM::Role",
            {
                "AssumeRolePolicyDocument": {
                    "Statement": assertions.Match.array_with(
                        [
                            assertions.Match.object_like(
                                {
                                    "Principal": {"Service": "ec2.amazonaws.com"},
                                }
                            )
                        ]
                    )
                },
                "ManagedPolicyArns": assertions.Match.array_with(
                    [
                        {
                            "Fn::Join": assertions.Match.any_value(),
                        }
                    ]
                ),
            },
        )

    def test_network_stack_links_ssm_client_and_endpoint_security_groups(self) -> None:
        """Edge: SSM client and endpoint SGs are restricted to HTTPS between them."""
        app = core.App()
        stack = Env4aiNetworkStack(app, "Env4aiNetworkStack", env=self._test_env())
        template = assertions.Template.from_stack(stack)

        template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {
                "GroupDescription": "Security group attached to instances that use Session Manager.",
                "SecurityGroupEgress": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "CidrIp": "0.0.0.0/0",
                                "IpProtocol": "-1",
                            }
                        )
                    ]
                ),
            },
        )
        template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {
                "GroupDescription": "Shared interface endpoint security group for SSM access.",
                "SecurityGroupIngress": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "FromPort": 443,
                                "ToPort": 443,
                                "IpProtocol": "tcp",
                            }
                        )
                    ]
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
        self.assertIn("SsmClientsSecurityGroupId", outputs)
        self.assertIn("SsmInstanceProfileArn", outputs)

    def test_network_stack_exports_stable_shared_resource_names(self) -> None:
        """Expected: workstation stacks can import shared-network resources by fixed export names."""
        app = core.App()
        stack = Env4aiNetworkStack(app, "Env4aiNetworkStack", env=self._test_env())
        outputs = assertions.Template.from_stack(stack).to_json()["Outputs"]

        self.assertEqual(
            get_shared_network_export_name("VpcId"),
            outputs["VpcId"]["Export"]["Name"],
        )
        self.assertEqual(
            get_shared_network_export_name("InternetGatewayId"),
            outputs["InternetGatewayId"]["Export"]["Name"],
        )
        self.assertEqual(
            get_shared_network_export_name("VpcCidr"),
            outputs["VpcCidr"]["Export"]["Name"],
        )
        self.assertEqual(
            get_shared_network_export_name("SsmClientsSecurityGroupId"),
            outputs["SsmClientsSecurityGroupId"]["Export"]["Name"],
        )
        self.assertEqual(
            get_shared_network_export_name("SsmInstanceProfileArn"),
            outputs["SsmInstanceProfileArn"]["Export"]["Name"],
        )


if __name__ == "__main__":
    unittest.main()
