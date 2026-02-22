#!/usr/bin/env python3
"""Find the newest workstation instance created by this stack and print SSH config help."""

from __future__ import annotations

import argparse
import configparser
from datetime import datetime
import os
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def parse_args() -> argparse.Namespace:
    name = Path.cwd().name

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
        default=f"{name.capitalize()}WorkstationStack",
        help="CloudFormation stack name.",
    )
    parser.add_argument(
        "--spot-fleet-logical-id",
        default=f"{name.capitalize()}SpotFleet",
        help="Logical ID of the Spot Fleet resource in the stack.",
    )
    parser.add_argument(
        "--ssh-host-alias",
        default=f"{name}-workstation",
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
    )


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

    if not public_ip:
        print("Public IP not assigned yet. Wait a moment, then run this script again.")
        return 1

    print(f"Public IP: {public_ip}")
    print("\nAdd this to ~/.ssh/config:\n")
    print(
        build_ssh_config_snippet(
            host_alias=args.ssh_host_alias,
            ip_address=public_ip,
            ssh_user=args.ssh_user,
            identity_file=args.identity_file,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
