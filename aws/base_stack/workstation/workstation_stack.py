from aws_cdk import (
    CfnOutput,
    CfnTag,
    Stack,
    aws_ec2 as ec2,
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


def _requires_public_ssh(access_mode: Literal["ssh", "ssm", "both"]) -> bool:
    """Return whether the access mode needs SSH-facing public connectivity."""
    return access_mode in {"ssh", "both"}


class WorkstationStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        shared_igw_id: str,
        shared_vpc: ec2.IVpc | None = None,
        shared_vpc_id: str | None = None,
        shared_vpc_cidr_block: str | None = None,
        availability_zone_index: int = 0,
        ami_id_override: str | None = None,
        ami_source: Literal["default", "selected"] | None = None,
        selected_ami_id: str | None = None,
        bootstrap_on_restored_ami: bool = False,
        verbose_bootstrap_resolution: bool = False,
        eip_allocation_id: str | None = None,
        access_mode: Literal["ssh", "ssm", "both"] = "ssh",
        public_ip_enabled: bool | None = None,
        shared_ssm_clients_security_group_id: str | None = None,
        shared_ssm_instance_profile_arn: str | None = None,
        environment_spec: EnvironmentSpec = ENVIRONMENT_SPEC,
        **kwargs,
    ) -> None:
        """Create the workstation infrastructure stack.

        Args:
            scope: Construct scope.
            construct_id: Logical construct id.
            shared_vpc: Shared VPC imported from ``Env4aiNetworkStack`` when already resolved.
            shared_igw_id: Shared Internet Gateway id from ``Env4aiNetworkStack``.
            shared_vpc_id: Shared VPC id used when the stack must import the VPC internally.
            shared_vpc_cidr_block: Shared VPC CIDR used with ``shared_vpc_id`` imports.
            availability_zone_index: Selected AZ index for workstation subnet.
            ami_id_override: Optional explicit AMI ID used for deploy-time restore flows.
            ami_source: AMI source mode for workstation launch. When unset, legacy
                ``ami_id_override`` behavior is preserved.
            selected_ami_id: Explicit AMI ID when using selected source mode.
            bootstrap_on_restored_ami: Opt-in to run full bootstrap for restored AMIs.
            verbose_bootstrap_resolution: Print resolved bootstrap script paths.
            eip_allocation_id: Optional Elastic IP allocation ID to track in stack outputs.
            access_mode: Workstation access mode (`ssh`, `ssm`, or `both`).
            public_ip_enabled: Explicit public IPv4 mapping override for outbound access.
            shared_ssm_clients_security_group_id: Shared SSM client SG ID from network stack.
            shared_ssm_instance_profile_arn: Shared SSM instance profile ARN from network stack.
            environment_spec: Canonical environment configuration and naming source.
            **kwargs: Additional ``Stack`` keyword args.
        """
        super().__init__(scope, construct_id, **kwargs)

        if access_mode not in {"ssh", "ssm", "both"}:
            raise ValueError("access_mode must be one of: ssh, ssm, both")
        if access_mode in {"ssm", "both"}:
            if not shared_ssm_clients_security_group_id:
                raise ValueError(
                    "shared_ssm_clients_security_group_id is required for access_mode 'ssm' or 'both'"
                )
            if not shared_ssm_instance_profile_arn:
                raise ValueError(
                    "shared_ssm_instance_profile_arn is required for access_mode 'ssm' or 'both'"
                )
        resolved_shared_vpc = shared_vpc
        if resolved_shared_vpc is None:
            if not shared_vpc_id:
                raise ValueError("shared_vpc or shared_vpc_id is required")
            if not shared_vpc_cidr_block:
                raise ValueError("shared_vpc_cidr_block is required when shared_vpc is not provided")
            resolved_shared_vpc = ec2.Vpc.from_vpc_attributes(
                self,
                "SharedNetworkVpc",
                availability_zones=[Stack.of(self).availability_zones[0]],
                vpc_id=shared_vpc_id,
                vpc_cidr_block=shared_vpc_cidr_block,
            )

        requires_public_ssh = _requires_public_ssh(access_mode)
        if public_ip_enabled is None:
            public_ip_enabled = requires_public_ssh
        if requires_public_ssh:
            public_ip_enabled = True

        if eip_allocation_id:
            CfnOutput(
                self,
                environment_spec.construct_id("EipAllocationId"),
                value=eip_allocation_id,
                description="Elastic IP allocation ID associated with this workstation.",
            )

        local_zone_subnet = ec2.CfnSubnet(self, environment_spec.construct_id("Subnet"),
            availability_zone=resolve_subnet_availability_zone(availability_zone_index),
            cidr_block=environment_spec.subnet_cidr,
            vpc_id=resolved_shared_vpc.vpc_id,
            map_public_ip_on_launch=public_ip_enabled
        )

        route_table = ec2.CfnRouteTable(
            self,
            environment_spec.construct_id("RouteTable"),
            vpc_id=resolved_shared_vpc.vpc_id,
        )
        ec2.CfnRoute(
            self,
            environment_spec.construct_id("DefaultRoute"),
            route_table_id=route_table.ref,
            destination_cidr_block="0.0.0.0/0",
            gateway_id=shared_igw_id,
        )
        ec2.CfnSubnetRouteTableAssociation(
            self,
            environment_spec.construct_id("SubnetRouteTableAssociation"),
            subnet_id=local_zone_subnet.ref,
            route_table_id=route_table.ref,
        )

        ssh_sg = ec2.SecurityGroup(
            self,
            environment_spec.construct_id("SshSecurityGroup"),
            vpc=resolved_shared_vpc,
        )
        if requires_public_ssh:
            allowed_ssh_cidr = environment_spec.resolved_allowed_ssh_cidr
            ssh_peer = (
                ec2.Peer.ipv4(allowed_ssh_cidr)
                if allowed_ssh_cidr is not None
                else ec2.Peer.any_ipv4()
            )
            ssh_sg.add_ingress_rule(ssh_peer, ec2.Port.tcp(22), "Allow SSH")

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

        security_group_ids: list[str] = []
        if requires_public_ssh:
            security_group_ids.append(ssh_sg.security_group_id)
        if access_mode in {"ssm", "both"} and shared_ssm_clients_security_group_id:
            security_group_ids.append(shared_ssm_clients_security_group_id)

        launch_specification = build_spot_fleet_launch_specification(
            ami_id=ami_id,
            instance_type=environment_spec.instance_type,
            security_group_ids=security_group_ids,
            subnet_id=local_zone_subnet.ref,
            volume_size=environment_spec.volume_size,
            include_bootstrap_user_data=should_include_bootstrap,
            bootstrap_files=environment_spec.bootstrap_files,
            key_name="aws_key" if requires_public_ssh else None,
            iam_instance_profile_arn=(
                shared_ssm_instance_profile_arn if access_mode in {"ssm", "both"} else None
            ),
            verbose_bootstrap_resolution=verbose_bootstrap_resolution,
        )
        launch_specification["tag_specifications"] = [
            ec2.CfnSpotFleet.SpotFleetTagSpecificationProperty(
                resource_type="instance",
                tags=[
                    CfnTag(key="Name", value=environment_spec.construct_id("")),
                ],
            )
        ]

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
