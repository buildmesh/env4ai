"""Shared AMI lifecycle helpers for workstation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import os
import sys
import time
from typing import Any, Callable, Mapping, Sequence, TextIO

from botocore.client import BaseClient
from botocore.exceptions import ClientError

LOGGER = logging.getLogger(__name__)
REQUIRED_AMI_READ_PERMISSIONS: tuple[str, ...] = ("ec2:DescribeImages",)


@dataclass(frozen=True, slots=True)
class AmiModeConfig:
    """AMI mode settings resolved from environment variables.

    Args:
        ami_load_tag: Exact AMI tag requested via ``AMI_LOAD``.
        ami_list: Whether AMI list mode is enabled.
        ami_pick: Whether list-and-pick mode is enabled.
        ami_bootstrap: Whether bootstrap should run for restored AMI deploys.
    """

    ami_load_tag: str
    ami_list: bool
    ami_pick: bool
    ami_bootstrap: bool


@dataclass(frozen=True, slots=True)
class AmiSelectionResult:
    """Result of AMI selection resolution for deploy orchestration.

    Args:
        selected_ami_id: AMI ID selected for deploy, when applicable.
        should_deploy: Whether deploy should continue after AMI action.
    """

    selected_ami_id: str | None
    should_deploy: bool


def is_truthy(value: str | None) -> bool:
    """Interpret common truthy string values."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def read_ami_mode_from_env(env: Mapping[str, str] | None = None) -> AmiModeConfig:
    """Read AMI mode controls from the provided environment mapping.

    Args:
        env: Optional environment mapping to read from.

    Returns:
        Parsed AMI mode configuration.
    """
    environment = env or os.environ
    return AmiModeConfig(
        ami_load_tag=str(environment.get("AMI_LOAD", "")).strip(),
        ami_list=is_truthy(environment.get("AMI_LIST")),
        ami_pick=is_truthy(environment.get("AMI_PICK")),
        ami_bootstrap=is_truthy(environment.get("AMI_BOOTSTRAP")),
    )


def validate_mode_arguments(ami_load_tag: str, ami_list: bool, ami_pick: bool) -> None:
    """Validate mutually exclusive AMI mode inputs.

    Args:
        ami_load_tag: AMI tag from ``AMI_LOAD`` environment variable.
        ami_list: Whether list mode is enabled.
        ami_pick: Whether list-and-pick mode is enabled.

    Raises:
        RuntimeError: If invalid combinations are provided.
    """
    if ami_pick and not ami_list:
        raise RuntimeError("AMI_PICK requires AMI_LIST=1.")
    if ami_load_tag and ami_list:
        raise RuntimeError("AMI_LOAD cannot be used together with AMI_LIST.")


def build_ami_lookup_error_message(scope: str) -> str:
    """Return a consistent user-facing AMI lookup failure message."""
    return (
        f"Unable to {scope} because AMI lookup failed. "
        "Verify AWS credentials, region, and ec2:DescribeImages permission."
    )


def _is_access_denied_error(error_code: str) -> bool:
    """Return whether an AWS error code indicates missing IAM permissions."""
    normalized = error_code.strip()
    return normalized in {
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
        "UnauthorizedException",
    }


def _raise_permission_preflight_error(action: str, error: ClientError) -> None:
    """Raise an actionable permission error for AMI-read failures.

    Args:
        action: Human-readable action that failed.
        error: Original AWS client error.

    Raises:
        RuntimeError: Always raised with remediation guidance.
    """
    error_code = str(error.response.get("Error", {}).get("Code", "Unknown"))
    if not _is_access_denied_error(error_code):
        raise RuntimeError(f"EC2 API call failed during {action}: {error}") from error

    permission_list = ", ".join(REQUIRED_AMI_READ_PERMISSIONS)
    raise RuntimeError(
        f"IAM preflight failed for {action}. Missing required EC2 image permission(s): "
        f"{permission_list}. "
        "Grant these actions to the deploy identity and retry."
    ) from error


def run_ami_permission_preflight(ec2_client: BaseClient, environment: str) -> None:
    """Verify required AMI-read IAM permissions before deploy mutation actions.

    Args:
        ec2_client: Boto3 EC2 client.
        environment: Environment name used for AMI name prefix filters.

    Raises:
        RuntimeError: If preflight fails due to missing permissions or API errors.
    """
    try:
        ec2_client.describe_images(
            Owners=["self"],
            Filters=[{"Name": "name", "Values": [f"{environment}_*"]}],
        )
    except ClientError as error:
        _raise_permission_preflight_error("AMI IAM preflight", error)


def list_environment_images(ec2_client: BaseClient, environment: str) -> list[dict[str, str]]:
    """List AMIs matching ``<environment>_*`` with key metadata.

    Args:
        ec2_client: Boto3 EC2 client.
        environment: Environment prefix in AMI names.

    Returns:
        Sorted AMI records (newest first).
    """
    pattern = f"{environment}_*"
    try:
        response = ec2_client.describe_images(
            Owners=["self"],
            Filters=[{"Name": "name", "Values": [pattern]}],
        )
    except Exception as err:
        if isinstance(err, ClientError):
            _raise_permission_preflight_error("AMI list mode", err)
        LOGGER.exception(
            "AMI list describe_images failed for environment=%s pattern=%s",
            environment,
            pattern,
        )
        raise RuntimeError(build_ami_lookup_error_message(f"list AMIs for '{environment}'")) from err

    images = response.get("Images", [])
    normalized: list[dict[str, str]] = []
    for image in images:
        normalized.append(
            {
                "image_id": str(image.get("ImageId", "")),
                "name": str(image.get("Name", "")),
                "state": str(image.get("State", "unknown")),
                "creation_date": str(image.get("CreationDate", "")),
            }
        )
    normalized.sort(key=lambda image: image["creation_date"], reverse=True)
    return normalized


def resolve_exact_image_id(ec2_client: BaseClient, expected_name: str) -> str:
    """Resolve an AMI ID by exact AMI name.

    Args:
        ec2_client: Boto3 EC2 client.
        expected_name: Exact expected AMI name.

    Returns:
        Matched AMI ID.

    Raises:
        RuntimeError: If no exact match exists.
    """
    try:
        response = ec2_client.describe_images(
            Owners=["self"],
            Filters=[{"Name": "name", "Values": [expected_name]}],
        )
    except Exception as err:
        if isinstance(err, ClientError):
            _raise_permission_preflight_error("AMI exact-name lookup", err)
        LOGGER.exception("AMI load describe_images failed for expected_name=%s", expected_name)
        raise RuntimeError(build_ami_lookup_error_message(f"load AMI '{expected_name}'")) from err

    candidates = response.get("Images", [])
    exact_matches = [image for image in candidates if str(image.get("Name", "")) == expected_name]
    if not exact_matches:
        raise RuntimeError(
            f"Requested AMI '{expected_name}' was not found. Deploy aborted before Spot request creation."
        )
    exact_matches.sort(key=lambda image: str(image.get("CreationDate", "")), reverse=True)
    image_id = str(exact_matches[0].get("ImageId", "")).strip()
    if not image_id:
        raise RuntimeError(f"Requested AMI '{expected_name}' is missing ImageId metadata.")
    return image_id


def print_image_list(images: Sequence[dict[str, str]], out: TextIO = sys.stdout) -> None:
    """Print numbered AMI list with state visibility."""
    if not images:
        out.write("No matching AMIs found.\n")
        return
    out.write("Available AMIs:\n")
    for index, image in enumerate(images, start=1):
        out.write(
            f"{index}. {image['name']} ({image['image_id']}) "
            f"state={image['state']} created={image['creation_date']}\n"
        )


def pick_image_interactively(
    images: Sequence[dict[str, str]],
    input_func: Callable[[str], str] = input,
    out: TextIO = sys.stdout,
) -> dict[str, str]:
    """Prompt user to choose an AMI from a numbered list.

    Args:
        images: Candidate AMI metadata list.
        input_func: Input provider for testability.
        out: Output stream for prompt guidance.

    Returns:
        Selected image metadata record.

    Raises:
        RuntimeError: If list is empty or selection is cancelled.
    """
    if not images:
        raise RuntimeError("AMI_PICK requested but no environment-scoped AMIs are available.")

    while True:
        response = input_func("Select AMI number to deploy (or 'q' to cancel): ").strip()
        if response.lower() == "q":
            raise RuntimeError("AMI selection cancelled.")
        if not response.isdigit():
            out.write("Invalid selection. Enter a number from the list.\n")
            continue
        index = int(response)
        if index < 1 or index > len(images):
            out.write("Selection out of range. Try again.\n")
            continue
        return images[index - 1]


def resolve_ami_selection(
    ec2_client: BaseClient,
    environment_key: str,
    mode: AmiModeConfig,
    input_func: Callable[[str], str] = input,
    out: TextIO = sys.stdout,
) -> AmiSelectionResult:
    """Resolve AMI behavior for deploy based on AMI lifecycle flags.

    Args:
        ec2_client: Boto3 EC2 client.
        environment_key: Canonical environment key used for AMI names.
        mode: AMI mode config.
        input_func: Input provider for interactive selection.
        out: Output stream used for list/pick feedback.

    Returns:
        AMI selection result used by deploy orchestration.
    """
    validate_mode_arguments(
        ami_load_tag=mode.ami_load_tag,
        ami_list=mode.ami_list,
        ami_pick=mode.ami_pick,
    )

    should_check_ami_permissions = bool(mode.ami_load_tag or mode.ami_list)
    if should_check_ami_permissions:
        run_ami_permission_preflight(ec2_client, environment=environment_key)

    if mode.ami_load_tag:
        expected_name = f"{environment_key}_{mode.ami_load_tag}"
        selected_ami_id = resolve_exact_image_id(ec2_client, expected_name=expected_name)
        out.write(f"Resolved AMI {expected_name} -> {selected_ami_id}\n")
        return AmiSelectionResult(selected_ami_id=selected_ami_id, should_deploy=True)

    if mode.ami_list:
        images = list_environment_images(ec2_client, environment=environment_key)
        print_image_list(images, out=out)
        if not mode.ami_pick:
            return AmiSelectionResult(selected_ami_id=None, should_deploy=False)
        selected_image = pick_image_interactively(images, input_func=input_func, out=out)
        out.write(
            f"Selected AMI {selected_image['name']} "
            f"({selected_image['image_id']}) for deploy.\n"
        )
        return AmiSelectionResult(
            selected_ami_id=selected_image["image_id"],
            should_deploy=True,
        )

    return AmiSelectionResult(selected_ami_id=None, should_deploy=True)


def resolve_running_instance_id(
    cloudformation_client: Any,
    ec2_client: Any,
    *,
    stack_name: str,
    spot_fleet_logical_id: str,
) -> str:
    """Resolve the newest running Spot Fleet instance id for a stack."""
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

    instances = [
        instance
        for reservation in described.get("Reservations", [])
        for instance in reservation.get("Instances", [])
        if str(instance.get("State", {}).get("Name", "")).strip() == "running"
    ]
    if not instances:
        raise RuntimeError("No running instances found for stack Spot Fleet.")

    def launch_time(instance: dict[str, Any]) -> datetime:
        value = instance.get("LaunchTime")
        return value if isinstance(value, datetime) else datetime.min

    instance_id = str(max(instances, key=launch_time).get("InstanceId", "")).strip()
    if not instance_id:
        raise RuntimeError("Resolved running instance is missing InstanceId.")
    return instance_id


def create_image_from_instance(ec2_client: Any, *, instance_id: str, image_name: str) -> str:
    """Create an AMI from an instance and return the AMI id."""
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
    """Wait until an AMI reaches ``available`` or fail on timeout/error."""
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
