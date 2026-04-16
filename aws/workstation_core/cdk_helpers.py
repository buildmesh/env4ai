"""Utilities for shared CDK naming and workstation launch derivation."""

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from workstation_core.environment_config import EnvironmentSpec


@dataclass(frozen=True, slots=True)
class CdkTarget:
    """Reusable CDK target descriptor.

    Args:
        stack_name: Final CloudFormation stack name.
        region: AWS region for deployment.
    """

    stack_name: str
    region: str


def build_stack_name(stack_prefix: str, environment: str) -> str:
    """Build a stable stack name from shared naming inputs.

    Args:
        stack_prefix: Prefix used across workstation stacks.
        environment: Environment key appended to the prefix.

    Returns:
        Stack name in ``{prefix}-{environment}`` format.

    Raises:
        ValueError: If either input is empty after trimming.
    """
    normalized_prefix = stack_prefix.strip()
    normalized_environment = environment.strip()
    if not normalized_prefix:
        raise ValueError("stack_prefix must be non-empty.")
    if not normalized_environment:
        raise ValueError("environment must be non-empty.")
    return f"{normalized_prefix}-{normalized_environment}"


def _require_aws_cdk() -> tuple[Any, Any]:
    """Import CDK modules on demand for helpers that require them.

    Returns:
        Tuple of ``(Fn, ec2)`` CDK modules.

    Raises:
        RuntimeError: If AWS CDK libraries are unavailable.
    """
    try:
        from aws_cdk import Fn
        from aws_cdk import aws_ec2 as ec2
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "aws_cdk is required for CDK helper operations in this environment."
        ) from exc
    return Fn, ec2


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
    Fn, _ = _require_aws_cdk()
    return Fn.select(availability_zone_index, Fn.get_azs())


def _resolve_bootstrap_script_path(filename: str, *, verbose_resolution: bool = False) -> Path:
    """Resolve a bootstrap script from environment-local or shared init paths.

    Args:
        filename: Bootstrap script filename declared in ``EnvironmentSpec``.
        verbose_resolution: Whether to print the resolved path for each script.

    Returns:
        Absolute path to the selected bootstrap script.

    Raises:
        FileNotFoundError: If the script is absent from both search locations.
    """
    environment_dir = Path.cwd().resolve()
    local_script_path = environment_dir / "init" / filename
    shared_script_path = environment_dir.parent / "common" / "init" / filename

    local_exists = local_script_path.is_file()
    shared_exists = shared_script_path.is_file()

    if local_exists and shared_exists:
        print(
            "bootstrap: "
            f"{filename} found in both {local_script_path} and {shared_script_path}; "
            f"using {local_script_path}"
        )
        return local_script_path

    if local_exists:
        if verbose_resolution:
            print(f"bootstrap: {filename} -> {local_script_path}")
        return local_script_path

    if shared_exists:
        if verbose_resolution:
            print(f"bootstrap: {filename} -> {shared_script_path}")
        return shared_script_path

    raise FileNotFoundError(
        f"Bootstrap script '{filename}' was not found. "
        f"Searched: {local_script_path}, {shared_script_path}"
    )


def build_bootstrap_user_data(
    bootstrap_files: tuple[str, ...],
    *,
    verbose_resolution: bool = False,
) -> str:
    """Build a base64-encoded userData script from ordered init files.

    Args:
        bootstrap_files: Ordered init script filenames to concatenate.
        verbose_resolution: Whether to print resolved bootstrap script paths.

    Returns:
        Base64-encoded bootstrap script payload.
    """
    user_data_script = ""
    for filename in bootstrap_files:
        script_path = _resolve_bootstrap_script_path(
            filename,
            verbose_resolution=verbose_resolution,
        )
        user_data_script += script_path.read_text(encoding="utf-8")
    return base64.b64encode(user_data_script.encode("utf-8")).decode("utf-8")


def resolve_ami_id(
    stack: object,
    environment_spec: EnvironmentSpec,
    ami_source: Literal["default", "selected"] = "default",
    selected_ami_id: str | None = None,
) -> str:
    """Resolve the AMI ID used by workstation launch specifications.

    Args:
        stack: Parent stack used for CDK AMI lookup context.
        environment_spec: Canonical environment AMI selector configuration.
        ami_source: AMI selection mode.
        selected_ami_id: Explicit AMI ID when ``ami_source`` is ``selected``.

    Returns:
        AMI ID to use for launch.

    Raises:
        ValueError: If AMI input values are invalid.
    """
    if ami_source == "default":
        _, ec2 = _require_aws_cdk()
        selector = environment_spec.default_ami_selector
        ubuntu_ami = ec2.MachineImage.lookup(
            name=selector.name,
            owners=[selector.owner],
            filters={key: list(value) for key, value in selector.filters.items()},
        )
        return ubuntu_ami.get_image(stack).image_id

    if ami_source == "selected":
        if not selected_ami_id or not selected_ami_id.strip():
            raise ValueError("selected_ami_id is required when ami_source is 'selected'")
        return selected_ami_id.strip()

    raise ValueError("ami_source must be either 'default' or 'selected'")


def build_spot_fleet_launch_specification(
    *,
    ami_id: str,
    instance_type: str,
    security_group_ids: list[str],
    subnet_id: str,
    volume_size: int,
    include_bootstrap_user_data: bool,
    bootstrap_files: tuple[str, ...],
    key_name: str | None = "aws_key",
    iam_instance_profile_arn: str | None = None,
    verbose_bootstrap_resolution: bool = False,
) -> dict[str, object]:
    """Build a reusable Spot Fleet launch specification payload.

    Args:
        ami_id: AMI ID for fleet launches.
        instance_type: EC2 instance type.
        security_group_ids: Security group IDs to attach.
        subnet_id: Subnet ID for fleet launches.
        volume_size: Root volume size in GiB.
        include_bootstrap_user_data: Whether to include bootstrap scripts.
        bootstrap_files: Ordered init script filenames.
        key_name: Optional EC2 key pair name.
        iam_instance_profile_arn: Optional EC2 instance profile ARN.
        verbose_bootstrap_resolution: Whether to print resolved bootstrap paths.

    Returns:
        Launch specification payload compatible with CDK Spot Fleet constructs.
    """
    launch_specification: dict[str, object] = {
        "image_id": ami_id,
        "instance_type": instance_type,
        "security_groups": [{"groupId": group_id} for group_id in security_group_ids],
        "subnet_id": subnet_id,
        "block_device_mappings": [
            {
                "deviceName": "/dev/sda1",
                "ebs": {
                    "deleteOnTermination": True,
                    "volumeSize": volume_size,
                    "volumeType": "gp3",
                    "encrypted": False,
                },
            }
        ],
    }
    if key_name:
        launch_specification["key_name"] = key_name
    if iam_instance_profile_arn:
        launch_specification["iam_instance_profile"] = {"arn": iam_instance_profile_arn}
    if include_bootstrap_user_data:
        launch_specification["user_data"] = build_bootstrap_user_data(
            bootstrap_files,
            verbose_resolution=verbose_bootstrap_resolution,
        )
    return launch_specification
