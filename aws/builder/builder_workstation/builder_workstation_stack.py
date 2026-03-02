from aws_cdk import (
    CfnOutput,
    Fn,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
)
from constructs import Construct
import base64
from pathlib import Path

from environment_config import BUILDER_ENVIRONMENT_SPEC
from workstation_core import EnvironmentSpec

def resolve_subnet_availability_zone(availability_zone_index: int = 0) -> str:
    """Return a dynamic AZ token from the deployment region.

    Args:
        availability_zone_index: The zero-based index into region AZs.

    Returns:
        A CloudFormation token selecting an AZ from ``Fn::GetAZs``.

    Raises:
        ValueError: If ``availability_zone_index`` is negative.
    """
    if availability_zone_index < 0:
        raise ValueError("availability_zone_index must be greater than or equal to 0")

    return Fn.select(availability_zone_index, Fn.get_azs())


class BuilderWorkstationStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        availability_zone_index: int = 0,
        environment_spec: EnvironmentSpec = BUILDER_ENVIRONMENT_SPEC,
        **kwargs,
    ) -> None:
        """Create the workstation infrastructure stack.

        Args:
            scope: Construct scope.
            construct_id: Logical construct id.
            availability_zone_index: Selected AZ index for workstation subnet.
            environment_spec: Canonical environment configuration and naming source.
            **kwargs: Additional ``Stack`` keyword args.
        """
        super().__init__(scope, construct_id, **kwargs)

        # Create a new VPC using environment-derived naming.
        vpc = ec2.Vpc(self, environment_spec.construct_id("VPC"),
            max_azs=1,
            subnet_configuration=[]
        )

        igw = ec2.CfnInternetGateway(self, environment_spec.construct_id("IGW"))
        ec2.CfnVPCGatewayAttachment(
            self,
            environment_spec.construct_id("IGWAttachment"),
            vpc_id=vpc.vpc_id,
            internet_gateway_id=igw.ref,
        )

        local_zone_subnet = ec2.CfnSubnet(self, environment_spec.construct_id("Subnet"),
            availability_zone=resolve_subnet_availability_zone(availability_zone_index),
            cidr_block="10.0.100.0/24",
            vpc_id=vpc.vpc_id,
            map_public_ip_on_launch=True
        )

        route_table = ec2.CfnRouteTable(self, environment_spec.construct_id("RouteTable"), vpc_id=vpc.vpc_id)
        ec2.CfnRoute(
            self,
            environment_spec.construct_id("DefaultRoute"),
            route_table_id=route_table.ref,
            destination_cidr_block="0.0.0.0/0",
            gateway_id=igw.ref,
        )
        ec2.CfnSubnetRouteTableAssociation(
            self,
            environment_spec.construct_id("SubnetRouteTableAssociation"),
            subnet_id=local_zone_subnet.ref,
            route_table_id=route_table.ref,
        )

        # Security group for SSH (VNC tunneled over SSH)
        sg = ec2.SecurityGroup(self, environment_spec.construct_id("SG"), vpc=vpc)
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "Allow SSH")

        # Find latest Ubuntu 22.04 LTS AMI
        selector = environment_spec.default_ami_selector
        ubuntu_ami = ec2.MachineImage.lookup(
            name=selector.name,
            owners=[selector.owner],
            filters={key: list(value) for key, value in selector.filters.items()},
        )

        ami_id = ubuntu_ami.get_image(self).image_id

        # User data script to install required tools and set up VNC
        user_data_script = ""
        for filename in environment_spec.bootstrap_files:
            script_path = Path("init") / filename
            user_data_script += script_path.read_text(encoding="utf-8")

        user_data_base64 = base64.b64encode(user_data_script.encode("utf-8")).decode("utf-8")

        # Spot Fleet Request
        ec2.CfnSpotFleet(self, environment_spec.spot_fleet_logical_id,
            spot_fleet_request_config_data=ec2.CfnSpotFleet.SpotFleetRequestConfigDataProperty(
                iam_fleet_role="arn:aws:iam::{}:role/aws-ec2-spot-fleet-tagging-role".format(self.account),
                target_capacity=1,
                spot_price=environment_spec.spot_price,
                launch_specifications=[
                    ec2.CfnSpotFleet.SpotFleetLaunchSpecificationProperty(
                        image_id=ami_id,
                        instance_type=environment_spec.instance_type,
                        key_name="aws_key",
                        security_groups=[{"groupId": sg.security_group_id}],
                        subnet_id=local_zone_subnet.ref,
                        user_data=user_data_base64,
                        block_device_mappings=[
                            {
                                "deviceName": "/dev/sda1",  # Typical root device for Ubuntu AMIs
                                "ebs": {
                                    "deleteOnTermination": True,
                                    "volumeSize": environment_spec.volume_size,
                                    "volumeType": "gp3",     # Use gp3 for best price/performance
                                    "encrypted": False       # Set to True if encryption is required
                                }
                            }
                        ]
                    )
                ]
            )
        )
