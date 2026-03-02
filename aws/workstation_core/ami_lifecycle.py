"""AMI lifecycle helpers shared by workstation orchestration scripts."""

from __future__ import annotations

from datetime import datetime
import time
from typing import Any, Callable


def resolve_running_instance_id(
    cloudformation_client: Any,
    ec2_client: Any,
    *,
    stack_name: str,
    spot_fleet_logical_id: str,
) -> str:
    """Resolve the newest running instance id for the environment stack.

    Args:
        cloudformation_client: Boto3 CloudFormation client.
        ec2_client: Boto3 EC2 client.
        stack_name: Stack name containing the Spot Fleet resource.
        spot_fleet_logical_id: Spot Fleet logical id in the stack.

    Returns:
        Newest running instance id.

    Raises:
        RuntimeError: If no running instance can be resolved.
    """
    try:
        stack_resource = cloudformation_client.describe_stack_resource(
            StackName=stack_name,
            LogicalResourceId=spot_fleet_logical_id,
        )
    except Exception as err:
        raise RuntimeError(
            f"Failed to resolve Spot Fleet resource '{spot_fleet_logical_id}' in stack '{stack_name}'."
        ) from err

    physical_id = str(
        stack_resource.get("StackResourceDetail", {}).get("PhysicalResourceId", "")
    ).strip()
    if not physical_id:
        raise RuntimeError(
            f"Stack resource '{spot_fleet_logical_id}' in stack '{stack_name}' has no physical id."
        )

    try:
        fleet_instances = ec2_client.describe_spot_fleet_instances(
            SpotFleetRequestId=physical_id
        )
    except Exception as err:
        raise RuntimeError(
            f"Failed to list instances for Spot Fleet request '{physical_id}'."
        ) from err

    instance_ids = [
        str(item.get("InstanceId", "")).strip()
        for item in fleet_instances.get("ActiveInstances", [])
        if str(item.get("InstanceId", "")).strip()
    ]
    if not instance_ids:
        raise RuntimeError(f"No active instances found for Spot Fleet request '{physical_id}'.")

    try:
        described = ec2_client.describe_instances(InstanceIds=instance_ids)
    except Exception as err:
        raise RuntimeError("Failed to describe Spot Fleet instances.") from err

    instances: list[dict[str, Any]] = []
    for reservation in described.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            instances.append(instance)

    running_instances = [
        instance
        for instance in instances
        if str(instance.get("State", {}).get("Name", "")).strip() == "running"
    ]
    if not running_instances:
        raise RuntimeError("No running instances found for stack Spot Fleet.")

    def launch_time(instance: dict[str, Any]) -> datetime:
        value = instance.get("LaunchTime")
        if isinstance(value, datetime):
            return value
        return datetime.min

    newest = max(running_instances, key=launch_time)
    instance_id = str(newest.get("InstanceId", "")).strip()
    if not instance_id:
        raise RuntimeError("Resolved running instance is missing InstanceId.")
    return instance_id


def create_image_from_instance(ec2_client: Any, *, instance_id: str, image_name: str) -> str:
    """Create an AMI from an instance and return the resulting image id.

    Args:
        ec2_client: Boto3 EC2 client.
        instance_id: Source instance id.
        image_name: Deterministic AMI name.

    Returns:
        Created image id.

    Raises:
        RuntimeError: If image creation fails or returns no image id.
    """
    try:
        response = ec2_client.create_image(
            InstanceId=instance_id,
            Name=image_name,
            Description=f"Saved from {instance_id} during stop workflow.",
            NoReboot=True,
        )
    except Exception as err:
        raise RuntimeError(
            f"Failed to create AMI '{image_name}' from instance '{instance_id}'."
        ) from err

    image_id = str(response.get("ImageId", "")).strip()
    if not image_id:
        raise RuntimeError(
            f"CreateImage succeeded for '{image_name}' but no ImageId was returned."
        )
    return image_id


def wait_for_image_available(
    ec2_client: Any,
    *,
    image_id: str,
    timeout_seconds: int = 45 * 60,
    poll_interval_seconds: int = 15,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    """Wait until an AMI reaches available state.

    Args:
        ec2_client: Boto3 EC2 client.
        image_id: AMI identifier to monitor.
        timeout_seconds: Max wait duration.
        poll_interval_seconds: Poll cadence while pending.
        monotonic: Monotonic clock for testability.
        sleeper: Sleep function for testability.

    Raises:
        RuntimeError: If AMI creation fails or does not complete before timeout.
    """
    deadline = monotonic() + timeout_seconds
    while monotonic() <= deadline:
        try:
            response = ec2_client.describe_images(ImageIds=[image_id])
        except Exception as err:
            raise RuntimeError(f"Failed while waiting for AMI '{image_id}' state.") from err

        images = response.get("Images", [])
        if not images:
            raise RuntimeError(f"AMI '{image_id}' was not found while waiting for availability.")

        state = str(images[0].get("State", "")).strip()
        if state == "available":
            return
        if state in {"failed", "deregistered", "error"}:
            raise RuntimeError(f"AMI '{image_id}' entered terminal state '{state}'.")

        sleeper(poll_interval_seconds)

    raise RuntimeError(
        f"Timed out waiting for AMI '{image_id}' to become available after {timeout_seconds} seconds."
    )
