"""Shared orchestration contracts for workstation workflows."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable, Mapping


@dataclass(frozen=True, slots=True)
class OrchestrationPlan:
    """Minimal deployment orchestration contract.

    Args:
        environment: Logical environment identifier.
        stack_name: Stack name that will be deployed.
        action: High-level action name (for example ``deploy`` or ``destroy``).
    """

    environment: str
    stack_name: str
    action: str


@dataclass(frozen=True, slots=True)
class StopOrchestrationInputs:
    """Inputs for stop/destroy orchestration.

    Args:
        environment_key: Canonical environment key (for example ``gastown``).
        stack_name: CloudFormation stack name.
        spot_fleet_logical_id: Stack logical id for Spot Fleet lookup.
        ami_save: Whether AMI save-on-stop is enabled.
        ami_tag: User-provided AMI tag when save-on-stop is enabled.
    """

    environment_key: str
    stack_name: str
    spot_fleet_logical_id: str
    ami_save: bool
    ami_tag: str | None = None


def validate_plan(plan: OrchestrationPlan) -> None:
    """Validate orchestration contract fields.

    Args:
        plan: The plan to validate.

    Raises:
        ValueError: If a required field is empty after trimming.
    """
    if not plan.environment.strip():
        raise ValueError("OrchestrationPlan.environment must be non-empty.")
    if not plan.stack_name.strip():
        raise ValueError("OrchestrationPlan.stack_name must be non-empty.")
    if not plan.action.strip():
        raise ValueError("OrchestrationPlan.action must be non-empty.")


def is_truthy(value: str | None) -> bool:
    """Interpret common truthy string values."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_stop_ami_config(env: Mapping[str, str] | None = None) -> tuple[bool, str | None]:
    """Parse AMI save-on-stop flags from an environment mapping.

    Args:
        env: Optional environment mapping for testability.

    Returns:
        A tuple of ``(ami_save_enabled, ami_tag_or_none)``.

    Raises:
        RuntimeError: If save is enabled and ``AMI_TAG`` is missing.
    """
    source = env if env is not None else os.environ
    ami_save = is_truthy(source.get("AMI_SAVE"))
    ami_tag = source.get("AMI_TAG", "").strip()
    if ami_save and not ami_tag:
        raise RuntimeError("AMI_SAVE=1 requires AMI_TAG to be set.")
    return ami_save, (ami_tag or None)


def build_stop_image_name(environment_key: str, ami_tag: str) -> str:
    """Build deterministic stop-time AMI name ``<environment>_<tag>``."""
    env_key = environment_key.strip()
    normalized_tag = ami_tag.strip()
    if not env_key:
        raise ValueError("environment_key must be non-empty.")
    if not normalized_tag:
        raise ValueError("ami_tag must be non-empty.")
    return f"{env_key}_{normalized_tag}"


def validate_stop_inputs(inputs: StopOrchestrationInputs) -> None:
    """Validate required stop orchestration inputs."""
    if not inputs.environment_key.strip():
        raise ValueError("StopOrchestrationInputs.environment_key must be non-empty.")
    if not inputs.stack_name.strip():
        raise ValueError("StopOrchestrationInputs.stack_name must be non-empty.")
    if not inputs.spot_fleet_logical_id.strip():
        raise ValueError("StopOrchestrationInputs.spot_fleet_logical_id must be non-empty.")
    if inputs.ami_save and not (inputs.ami_tag or "").strip():
        raise ValueError("StopOrchestrationInputs.ami_tag must be set when ami_save is enabled.")


def run_stop_orchestration(
    inputs: StopOrchestrationInputs,
    *,
    resolve_running_instance_id: Callable[[], str],
    create_image: Callable[[str, str], str],
    wait_for_image_available: Callable[[str], None],
    destroy_stack: Callable[[], None],
) -> str | None:
    """Run stop-time AMI save orchestration and destroy gating.

    Args:
        inputs: Stop orchestration inputs.
        resolve_running_instance_id: Callback to resolve active instance id.
        create_image: Callback creating image from instance id and image name.
        wait_for_image_available: Callback waiting for AMI to become available.
        destroy_stack: Callback executing the destroy operation.

    Returns:
        Saved AMI id when AMI save is enabled, otherwise ``None``.

    Raises:
        RuntimeError: If save-on-stop fails.
    """
    validate_stop_inputs(inputs)

    saved_image_id: str | None = None
    if inputs.ami_save:
        image_name = build_stop_image_name(inputs.environment_key, inputs.ami_tag or "")
        instance_id = resolve_running_instance_id().strip()
        if not instance_id:
            raise RuntimeError("Unable to resolve a running instance for AMI save-on-stop.")
        saved_image_id = create_image(instance_id, image_name).strip()
        if not saved_image_id:
            raise RuntimeError("AMI save-on-stop failed: create_image returned an empty AMI id.")
        wait_for_image_available(saved_image_id)

    destroy_stack()
    return saved_image_id
