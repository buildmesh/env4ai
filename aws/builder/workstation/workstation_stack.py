from aws_cdk import (
    CfnOutput,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
)
from constructs import Construct
from typing import Literal

from environment_config import ENVIRONMENT_SPEC
from workstation_core import EnvironmentSpec
from workstation_core.cdk_helpers import (
    build_spot_fleet_launch_specification,
    resolve_ami_id,
    resolve_subnet_availability_zone,
)


class WorkstationStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        availability_zone_index: int = 0,
        ami_id_override: str | None = None,
        ami_source: Literal["default", "selected"] | None = None,
        selected_ami_id: str | None = None,
        bootstrap_on_restored_ami: bool = False,
        environment_spec: EnvironmentSpec = ENVIRONMENT_SPEC,
        **kwargs,
    ) -> None:
        """Create the workstation infrastructure stack.

        Args:
            scope: Construct scope.
            construct_id: Logical construct id.
            availability_zone_index: Selected AZ index for workstation subnet.
            ami_id_override: Optional explicit AMI ID used for deploy-time restore flows.
            ami_source: AMI source mode for workstation launch. When unset, legacy
                ``ami_id_override`` behavior is preserved.
            selected_ami_id: Explicit AMI ID when using selected source mode.
            bootstrap_on_restored_ami: Opt-in to run full bootstrap for restored AMIs.
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

        # Reason: preserve ``ami_id_override`` compatibility while supporting the
        # new ``ami_source``/``selected_ami_id`` API.
        effective_ami_source: Literal["default", "selected"]
        effective_selected_ami_id: str | None = selected_ami_id
        if ami_source is None:
            if ami_id_override and ami_id_override.strip():
                effective_ami_source = "selected"
                effective_selected_ami_id = ami_id_override.strip()
            else:
                effective_ami_source = "default"
        else:
            effective_ami_source = ami_source
            if (
                effective_ami_source == "selected"
                and ami_id_override
                and ami_id_override.strip()
            ):
                override_ami_id = ami_id_override.strip()
                if effective_ami_source == "selected":
                    if (
                        effective_selected_ami_id
                        and effective_selected_ami_id.strip()
                        and effective_selected_ami_id.strip() != override_ami_id
                    ):
                        raise ValueError("ami_id_override conflicts with selected_ami_id")
                    if not effective_selected_ami_id or not effective_selected_ami_id.strip():
                        effective_selected_ami_id = override_ami_id

        ami_id = resolve_ami_id(
            stack=self,
            environment_spec=environment_spec,
            ami_source=effective_ami_source,
            selected_ami_id=effective_selected_ami_id,
        )

        should_include_bootstrap = (
            effective_ami_source == "default"
            or (
                effective_ami_source == "selected"
                and bootstrap_on_restored_ami
            )
        )
        launch_specification = build_spot_fleet_launch_specification(
            ami_id=ami_id,
            instance_type=environment_spec.instance_type,
            security_group_id=sg.security_group_id,
            subnet_id=local_zone_subnet.ref,
            volume_size=environment_spec.volume_size,
            include_bootstrap_user_data=should_include_bootstrap,
            bootstrap_files=environment_spec.bootstrap_files,
        )

        # Spot Fleet Request
        ec2.CfnSpotFleet(self, environment_spec.spot_fleet_logical_id,
            spot_fleet_request_config_data=ec2.CfnSpotFleet.SpotFleetRequestConfigDataProperty(
                iam_fleet_role="arn:aws:iam::{}:role/aws-ec2-spot-fleet-tagging-role".format(self.account),
                target_capacity=1,
                spot_price=environment_spec.spot_price,
                launch_specifications=[
                    ec2.CfnSpotFleet.SpotFleetLaunchSpecificationProperty(**launch_specification)
                ]
            )
        )
