"""CDK stack that owns the shared env4ai VPC, Internet Gateway, and SSM resources."""

from __future__ import annotations

from aws_cdk import Annotations, CfnOutput, Fn, Stack, Tags, aws_ec2 as ec2, aws_iam as iam
from constructs import Construct

from workstation_core import get_shared_network_config

_SSM_ENDPOINT_SUBNET_CIDR = "10.0.250.0/24"
_EC2MESSAGES_UNSUPPORTED_REGIONS = frozenset(
    {
        "ap-east-2",
        "ap-southeast-5",
        "ap-southeast-7",
        "eu-central-2",
        "mx-central-1",
    }
)


def _supports_ec2messages_endpoint(region: str) -> bool:
    """Return whether ``ec2messages`` should be created in the given region."""
    normalized_region = region.strip()
    return bool(normalized_region) and normalized_region not in _EC2MESSAGES_UNSUPPORTED_REGIONS


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

        self.ssm_endpoint_subnet = ec2.PrivateSubnet(
            self,
            "SsmEndpointsSubnet",
            availability_zone=Fn.select(0, Fn.get_azs()),
            cidr_block=_SSM_ENDPOINT_SUBNET_CIDR,
            vpc_id=self.vpc.vpc_id,
        )

        self.ssm_endpoints_sg = ec2.SecurityGroup(
            self,
            "SsmEndpointsSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=True,
            description="Shared interface endpoint security group for SSM access.",
        )
        self.ssm_clients_sg = ec2.SecurityGroup(
            self,
            "SsmClientsSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=False,
            description="Security group attached to instances that use Session Manager.",
        )
        self.ssm_clients_sg.add_egress_rule(
            self.ssm_endpoints_sg,
            ec2.Port.tcp(443),
            "Allow HTTPS to SSM interface endpoints",
        )
        self.ssm_endpoints_sg.add_ingress_rule(
            self.ssm_clients_sg,
            ec2.Port.tcp(443),
            "Allow HTTPS from SSM clients",
        )

        self.ssm_instance_role = iam.Role(
            self,
            "SsmEc2InstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                )
            ],
        )
        self.ssm_instance_profile = iam.CfnInstanceProfile(
            self,
            "SsmEc2InstanceProfile",
            roles=[self.ssm_instance_role.role_name],
        )

        endpoint_subnets = ec2.SubnetSelection(subnets=[self.ssm_endpoint_subnet])
        endpoint_security_groups = [self.ssm_endpoints_sg]
        ec2.InterfaceVpcEndpoint(
            self,
            "SsmEndpoint",
            vpc=self.vpc,
            service=ec2.InterfaceVpcEndpointAwsService.SSM,
            subnets=endpoint_subnets,
            security_groups=endpoint_security_groups,
            private_dns_enabled=True,
        )
        ec2.InterfaceVpcEndpoint(
            self,
            "SsmMessagesEndpoint",
            vpc=self.vpc,
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            subnets=endpoint_subnets,
            security_groups=endpoint_security_groups,
            private_dns_enabled=True,
        )
        if _supports_ec2messages_endpoint(Stack.of(self).region):
            ec2.InterfaceVpcEndpoint(
                self,
                "Ec2MessagesEndpoint",
                vpc=self.vpc,
                service=ec2.InterfaceVpcEndpointAwsService.EC2_MESSAGES,
                subnets=endpoint_subnets,
                security_groups=endpoint_security_groups,
                private_dns_enabled=True,
            )
        else:
            Annotations.of(self).add_warning(
                "Skipping ec2messages endpoint because this region does not support it."
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
        CfnOutput(
            self,
            "SsmClientsSecurityGroupId",
            value=self.ssm_clients_sg.security_group_id,
            description="Shared security group for workstation SSM clients.",
        )
        CfnOutput(
            self,
            "SsmInstanceProfileArn",
            value=self.ssm_instance_profile.attr_arn,
            description="Shared EC2 instance profile for Session Manager access.",
        )
