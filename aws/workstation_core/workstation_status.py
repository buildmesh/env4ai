"""Shared status helpers for workstation lifecycle UX."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from workstation_core.ami_lifecycle import resolve_running_instance_id


@dataclass(frozen=True, slots=True)
class WorkstationStatus:
    """Summarized workstation status for interactive UX.

    Args:
        stack_state: High-level stack state (`not found`, `in progress`, `running`).
        stack_status: Raw CloudFormation stack status when available.
        instance_id: Running instance id when resolvable.
        public_ip: Running instance public IP when resolvable.
        ssh_alias: SSH host alias when running instance details are available.
    """

    stack_state: str
    stack_status: str | None = None
    instance_id: str | None = None
    public_ip: str | None = None
    ssh_alias: str | None = None


def _is_stack_not_found_error(error: Exception) -> bool:
    """Return true when an AWS exception indicates the stack does not exist."""
    response = getattr(error, "response", None)
    if isinstance(response, dict):
        code = str(response.get("Error", {}).get("Code", "")).strip()
        if code == "ValidationError":
            message = str(response.get("Error", {}).get("Message", "")).strip().lower()
            return "does not exist" in message
    return "does not exist" in str(error).lower()


def _is_runtime_instance_absence(error: RuntimeError) -> bool:
    """Return true when runtime errors indicate no running instance yet."""
    text = str(error).lower()
    return "no active instances found" in text or "no running instances found" in text


def _resolve_public_ip(ec2_client: Any, instance_id: str) -> str | None:
    """Resolve public IP for one instance id."""
    described = ec2_client.describe_instances(InstanceIds=[instance_id])
    for reservation in described.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            candidate_id = str(instance.get("InstanceId", "")).strip()
            if candidate_id == instance_id:
                public_ip = str(instance.get("PublicIpAddress", "")).strip()
                return public_ip or None
    return None


def get_workstation_status(
    cloudformation_client: Any,
    ec2_client: Any,
    *,
    stack_name: str,
    spot_fleet_logical_id: str,
    ssh_alias: str,
) -> WorkstationStatus:
    """Resolve typed stack/instance status for one workstation environment.

    Args:
        cloudformation_client: Boto3 CloudFormation client.
        ec2_client: Boto3 EC2 client.
        stack_name: CloudFormation stack name.
        spot_fleet_logical_id: Spot Fleet logical resource id.
        ssh_alias: SSH alias from the environment spec.

    Returns:
        Typed workstation status for interactive UX.

    Raises:
        RuntimeError: If status lookup fails for reasons other than missing stack/instance.
    """
    try:
        stack_response = cloudformation_client.describe_stacks(StackName=stack_name)
    except Exception as err:
        if _is_stack_not_found_error(err):
            return WorkstationStatus(stack_state="not found")
        raise RuntimeError(f"Failed to read stack status for '{stack_name}'.") from err

    stacks = stack_response.get("Stacks", [])
    stack_status = str(stacks[0].get("StackStatus", "")).strip() if stacks else ""
    normalized_stack_status = stack_status or None

    if stack_status.endswith("_IN_PROGRESS"):
        return WorkstationStatus(stack_state="in progress", stack_status=normalized_stack_status)

    try:
        instance_id = resolve_running_instance_id(
            cloudformation_client,
            ec2_client,
            stack_name=stack_name,
            spot_fleet_logical_id=spot_fleet_logical_id,
        )
    except RuntimeError as err:
        if _is_runtime_instance_absence(err):
            return WorkstationStatus(stack_state="in progress", stack_status=normalized_stack_status)
        raise RuntimeError(f"Failed to resolve running instance for '{stack_name}'.") from err

    try:
        public_ip = _resolve_public_ip(ec2_client, instance_id=instance_id)
    except Exception as err:
        raise RuntimeError(f"Failed to resolve instance metadata for '{instance_id}'.") from err

    return WorkstationStatus(
        stack_state="running",
        stack_status=normalized_stack_status,
        instance_id=instance_id,
        public_ip=public_ip,
        ssh_alias=ssh_alias,
    )
