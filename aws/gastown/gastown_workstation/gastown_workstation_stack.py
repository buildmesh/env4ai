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
from typing import Literal

from environment_config import GASTOWN_ENVIRONMENT_SPEC
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


def build_bootstrap_user_data(bootstrap_files: tuple[str, ...]) -> str:
    """Return base64-encoded bootstrap user data for fresh Ubuntu launches.

    Args:
        bootstrap_files: Ordered init script filenames to concatenate.

    Returns:
        Base64-encoded concatenation of init scripts.
    """
    user_data_script = ""
    for filename in bootstrap_files:
        script_path = Path("init") / filename
        user_data_script += script_path.read_text(encoding="utf-8")

    return base64.b64encode(user_data_script.encode("utf-8")).decode("utf-8")


def resolve_ami_id(
    stack: Stack,
    environment_spec: EnvironmentSpec,
    ami_source: Literal["default", "selected"] = "default",
    selected_ami_id: str | None = None,
) -> str:
    """Resolve the AMI ID to use for the workstation launch.

    Args:
        stack: Parent stack used for AMI lookup context.
        environment_spec: Canonical environment AMI selector config.
        ami_source: AMI selection mode.
        selected_ami_id: Explicit AMI ID for ``selected`` mode.

    Returns:
        AMI ID to use in the launch specification.

    Raises:
        ValueError: If AMI inputs are invalid.
    """
    if ami_source == "default":
        selector = environment_spec.default_ami_selector
        ubuntu_ami = ec2.MachineImage.lookup(
            name=selector.name,
            owners=[selector.owner],
            filters={key: list(value) for key, value in selector.filters.items()},
        )
        return ubuntu_ami.get_image(stack).image_id

    if ami_source == "selected":
        if not selected_ami_id or not selected_ami_id.strip():
            raise ValueError(
                "selected_ami_id is required when ami_source is 'selected'"
            )
        return selected_ami_id.strip()

    raise ValueError("ami_source must be either 'default' or 'selected'")


class GastownWorkstationStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        availability_zone_index: int = 0,
        ami_id_override: str | None = None,
        ami_source: Literal["default", "selected"] | None = None,
        selected_ami_id: str | None = None,
        bootstrap_on_restored_ami: bool = False,
        environment_spec: EnvironmentSpec = GASTOWN_ENVIRONMENT_SPEC,
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

        launch_specification: dict[str, object] = {
            "image_id": ami_id,
            "instance_type": environment_spec.instance_type,
            "key_name": "aws_key",
            "security_groups": [{"groupId": sg.security_group_id}],
            "subnet_id": local_zone_subnet.ref,
            "block_device_mappings": [
                {
                    "deviceName": "/dev/sda1",  # Typical root device for Ubuntu AMIs
                    "ebs": {
                        "deleteOnTermination": True,
                        "volumeSize": environment_spec.volume_size,
                        "volumeType": "gp3",     # Use gp3 for best price/performance
                        "encrypted": False       # Set to True if encryption is required
                    }
                }
            ],
        }
        if should_include_bootstrap:
            launch_specification["user_data"] = build_bootstrap_user_data(
                environment_spec.bootstrap_files
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
