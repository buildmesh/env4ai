#!/usr/bin/env python3
"""Find the newest workstation instance created by this stack and print SSH config help."""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for instance lookup."""
    parser = argparse.ArgumentParser(
        description="Look up the newest workstation instance and print SSH config guidance."
    )
    parser.add_argument("--region", default="us-west-2", help="AWS region to query.")
    parser.add_argument(
        "--profile",
        default=None,
        help="Optional AWS profile name. Uses default credential chain when omitted.",
    )
    parser.add_argument(
        "--stack-name",
        default="AwsWorkstationStack",
        help="CloudFormation stack name.",
    )
    parser.add_argument(
        "--spot-fleet-logical-id",
        default="WorkstationSpotFleet",
        help="Logical ID of the Spot Fleet resource in the stack.",
    )
    parser.add_argument(
        "--ssh-host-alias",
        default="gastown-workstation",
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
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
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
