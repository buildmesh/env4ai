#!/usr/bin/env python3
"""Find the newest workstation instance created by this stack and print SSH config help."""

from __future__ import annotations

import argparse
import configparser
from datetime import datetime
import importlib.util
import os
from pathlib import Path
from time import sleep
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def _load_environment_spec_from_cwd() -> Any | None:
    """Load ``ENVIRONMENT_SPEC`` from cwd-local ``environment_config.py``.

    Returns:
        Environment spec object when available, otherwise ``None``.
    """
    module_path = Path.cwd() / "environment_config.py"
    if not module_path.is_file():
        return None

    import_spec = importlib.util.spec_from_file_location(
        "active_environment_config",
        str(module_path),
    )
    if import_spec is None or import_spec.loader is None:
        return None
    module = importlib.util.module_from_spec(import_spec)
    import_spec.loader.exec_module(module)
    return getattr(module, "ENVIRONMENT_SPEC", None)


def parse_args() -> argparse.Namespace:
    name = Path.cwd().name
    environment_spec = _load_environment_spec_from_cwd()
    default_stack_name = f"{name.capitalize()}WorkstationStack"
    default_spot_fleet_logical_id = f"{name.capitalize()}SpotFleet"
    default_ssh_alias = f"{name}-workstation"
    default_access_mode = "ssh"
    if environment_spec is not None:
        default_stack_name = str(environment_spec.stack_name)
        default_spot_fleet_logical_id = str(environment_spec.spot_fleet_logical_id)
        default_ssh_alias = str(environment_spec.ssh_alias)
        default_access_mode = str(getattr(environment_spec, "default_access_mode", "ssh"))

    """Parse command-line arguments for instance lookup."""
    parser = argparse.ArgumentParser(
        description="Look up the newest workstation instance and print SSH config guidance."
    )
    parser.add_argument(
        "--region",
        default=None,
        help="Optional AWS region to query. Falls back to env vars or ~/.aws/config when omitted.",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Optional AWS profile name. Uses default credential chain when omitted.",
    )
    parser.add_argument(
        "--stack-name",
        default=default_stack_name,
        help="CloudFormation stack name.",
    )
    parser.add_argument(
        "--spot-fleet-logical-id",
        default=default_spot_fleet_logical_id,
        help="Logical ID of the Spot Fleet resource in the stack.",
    )
    parser.add_argument(
        "--ssh-host-alias",
        default=default_ssh_alias,
        help="Host alias to show in the SSH config snippet.",
    )
    parser.add_argument(
        "--ssh-user",
        default="ubuntu",
        help="SSH username to show in the SSH config snippet.",
    )
    parser.add_argument(
        "--identity-file",
        default="~/.ssh/aws_key.pem",
        help="SSH identity file path to show in the SSH config snippet.",
    )
    parser.add_argument(
        "--access-mode",
        choices=("ssh", "ssm", "both"),
        default=default_access_mode,
        help="Connection mode used for the deployed workstation.",
    )
    parser.add_argument(
        "--eip-allocation-id",
        default=None,
        help="Elastic IP allocation ID to associate with the instance.",
    )
    parser.add_argument(
        "--eip-public-ip",
        default=None,
        help="Elastic IP public IP address to show in SSH config (used with --eip-allocation-id).",
    )
    return parser.parse_args()


def normalize_optional(value: str | None) -> str | None:
    """Return stripped text when non-empty, otherwise None."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def get_profile_name(cli_profile: str | None, env: dict[str, str] | None = None) -> str:
    """Resolve the profile name from CLI, then environment, then default."""
    environment = env or os.environ
    return (
        normalize_optional(cli_profile)
        or normalize_optional(environment.get("AWS_PROFILE"))
        or "default"
    )


def get_profile_section_name(profile_name: str) -> str:
    """Map profile name to ~/.aws/config section name."""
    return "default" if profile_name == "default" else f"profile {profile_name}"


def load_region_from_config(profile_name: str, config_path: Path) -> str:
    """Load region for the given profile from ~/.aws/config."""
    if not config_path.is_file():
        raise RuntimeError(
            "Unable to resolve AWS region: ~/.aws/config was not found and no region was provided via --region, AWS_REGION, or AWS_DEFAULT_REGION."
        )

    parser = configparser.ConfigParser()
    parser.read(config_path)
    section_name = get_profile_section_name(profile_name)

    if not parser.has_section(section_name):
        raise RuntimeError(
            f"Unable to resolve AWS region: profile section '[{section_name}]' was not found in ~/.aws/config."
        )

    region = normalize_optional(parser.get(section_name, "region", fallback=None))
    if not region:
        raise RuntimeError(
            f"Unable to resolve AWS region: no 'region' value found in profile '[{profile_name}]' in ~/.aws/config."
        )
    return region


def get_region(
    cli_region: str | None,
    cli_profile: str | None,
    env: dict[str, str] | None = None,
    config_path: Path | None = None,
) -> str:
    """Resolve region from CLI, env vars, then ~/.aws/config for the active profile."""
    environment = env or os.environ
    explicit_region = normalize_optional(cli_region)
    if explicit_region:
        return explicit_region

    env_region = normalize_optional(environment.get("AWS_REGION")) or normalize_optional(
        environment.get("AWS_DEFAULT_REGION")
    )
    if env_region:
        return env_region

    profile_name = get_profile_name(cli_profile, environment)
    target_path = config_path or (Path.home() / ".aws" / "config")
    return load_region_from_config(profile_name=profile_name, config_path=target_path)


def get_spot_fleet_request_id(
    cloudformation_client: Any,
    stack_name: str,
    logical_resource_id: str,
) -> str:
    """Return Spot Fleet request ID from a stack logical resource ID."""
    try:
        response = cloudformation_client.describe_stack_resource(
            StackName=stack_name,
            LogicalResourceId=logical_resource_id,
        )
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(
            f"Failed to resolve stack resource '{logical_resource_id}' in stack '{stack_name}'."
        ) from exc

    detail = response.get("StackResourceDetail", {})
    physical_id = detail.get("PhysicalResourceId")
    if not physical_id:
        raise RuntimeError(
            f"Stack resource '{logical_resource_id}' in stack '{stack_name}' has no physical ID."
        )
    return physical_id


def get_newest_instance_for_spot_fleet(ec2_client: Any, spot_fleet_request_id: str) -> dict[str, Any]:
    """Return the newest launched EC2 instance attached to a Spot Fleet request."""
    try:
        fleet_response = ec2_client.describe_spot_fleet_instances(
            SpotFleetRequestId=spot_fleet_request_id
        )
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(
            f"Failed to list instances for Spot Fleet '{spot_fleet_request_id}'."
        ) from exc

    active_instances = fleet_response.get("ActiveInstances", [])
    instance_ids = [item["InstanceId"] for item in active_instances if item.get("InstanceId")]
    if not instance_ids:
        raise RuntimeError(
            f"No active instances found for Spot Fleet '{spot_fleet_request_id}'."
        )

    try:
        instance_response = ec2_client.describe_instances(InstanceIds=instance_ids)
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError("Failed to describe EC2 instances for the Spot Fleet.") from exc

    instances: list[dict[str, Any]] = []
    for reservation in instance_response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            instances.append(instance)

    if not instances:
        raise RuntimeError("Spot Fleet returned active instance IDs but EC2 returned no instance records.")

    def launch_time(instance: dict[str, Any]) -> datetime:
        value = instance.get("LaunchTime")
        if isinstance(value, datetime):
            return value
        return datetime.min

    return max(instances, key=launch_time)


def build_ssh_config_snippet(host_alias: str, ip_address: str, ssh_user: str, identity_file: str) -> str:
    """Build an SSH config snippet for user guidance."""
    return (
        f"Host {host_alias}\n"
        f"  HostName {ip_address}\n"
        f"  User {ssh_user}\n"
        f"  IdentityFile {identity_file}\n"
        f"  IdentitiesOnly yes\n"
    )


def build_ssm_start_session_command(region: str, instance_id: str, profile: str | None) -> str:
    """Build the AWS CLI command used to start an SSM session."""
    command = ["aws", "ssm", "start-session", "--region", region]
    if profile:
        command.extend(["--profile", profile])
    command.extend(["--target", instance_id])
    return " ".join(command)


def main() -> int:
    """Run instance lookup and print user-facing connection instructions."""
    args = parse_args()
    try:
        region = get_region(cli_region=args.region, cli_profile=args.profile)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    session = boto3.Session(profile_name=normalize_optional(args.profile), region_name=region)
    ec2_client = session.client("ec2")
    cloudformation_client = session.client("cloudformation")

    try:
        spot_fleet_request_id = get_spot_fleet_request_id(
            cloudformation_client=cloudformation_client,
            stack_name=args.stack_name,
            logical_resource_id=args.spot_fleet_logical_id,
        )
        instance = get_newest_instance_for_spot_fleet(
            ec2_client=ec2_client,
            spot_fleet_request_id=spot_fleet_request_id,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    instance_id = instance.get("InstanceId", "unknown")
    state = instance.get("State", {}).get("Name", "unknown")
    launch_time = instance.get("LaunchTime")
    public_ip = instance.get("PublicIpAddress")

    print(f"Newest instance: {instance_id} [{state}]")
    print(f"Region: {region}")
    if launch_time:
        print(f"Launch time: {launch_time}")

    access_mode = normalize_optional(args.access_mode) or "ssh"
    eip_allocation_id = normalize_optional(args.eip_allocation_id)
    eip_public_ip = normalize_optional(args.eip_public_ip)

    if eip_allocation_id:
        if not public_ip:
            print("Public IP not assigned yet; cannot associate Elastic IP. Wait a moment, then run this script again.")
            return 1
        try:
            sleep(5)
            ec2_client.associate_address(
                AllocationId=eip_allocation_id,
                InstanceId=instance_id,
                AllowReassociation=True,
            )
            print(f"Elastic IP associated: {eip_public_ip or eip_allocation_id}")
        except (BotoCoreError, ClientError) as exc:
            print(f"Warning: Elastic IP association failed: {exc}")
        # Reason: use the stable EIP address for SSH config when available.
        display_ip = eip_public_ip or public_ip
    else:
        display_ip = public_ip

    if access_mode in {"ssm", "both"}:
        print("\nStart an SSM session:\n")
        print(
            build_ssm_start_session_command(
                region=region,
                instance_id=instance_id,
                profile=normalize_optional(args.profile),
            )
        )

    if access_mode == "ssm":
        return 0

    if not display_ip:
        print("Public IP not assigned yet. Wait a moment, then run this script again.")
        return 1

    print(f"Public IP: {display_ip}")
    print("\nAdd this to ~/.ssh/config:\n")
    print(
        build_ssh_config_snippet(
            host_alias=args.ssh_host_alias,
            ip_address=display_ip,
            ssh_user=args.ssh_user,
            identity_file=args.identity_file,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
