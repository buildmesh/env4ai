"""CDK stack that owns the shared env4ai VPC and Internet Gateway."""

from __future__ import annotations

from aws_cdk import CfnOutput, Stack, Tags, aws_ec2 as ec2
from constructs import Construct

from workstation_core import get_shared_network_config


class Env4aiNetworkStack(Stack):
    """Shared network stack for all workstation environments."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """Create the shared VPC and Internet Gateway resources.

        Args:
            scope: Construct scope.
            construct_id: Logical construct id.
            **kwargs: Additional ``Stack`` keyword args.
        """
        super().__init__(scope, construct_id, **kwargs)

        shared_network = get_shared_network_config()
        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            ip_addresses=ec2.IpAddresses.cidr(shared_network.vpc_cidr),
            max_azs=1,
            subnet_configuration=[],
        )
        Tags.of(self.vpc).add("Name", shared_network.vpc_name, priority=300)

        self.internet_gateway = ec2.CfnInternetGateway(self, "InternetGateway")
        self.internet_gateway.tags.set_tag("Name", shared_network.igw_name)
        ec2.CfnVPCGatewayAttachment(
            self,
            "InternetGatewayAttachment",
            vpc_id=self.vpc.vpc_id,
            internet_gateway_id=self.internet_gateway.ref,
        )

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id, description="Shared env4ai VPC id.")
        CfnOutput(
            self,
            "InternetGatewayId",
            value=self.internet_gateway.ref,
            description="Shared env4ai Internet Gateway id.",
        )
        CfnOutput(
            self,
            "VpcCidr",
            value=shared_network.vpc_cidr,
            description="Shared env4ai VPC CIDR.",
        )
