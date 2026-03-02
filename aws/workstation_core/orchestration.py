"""Shared deploy and stop orchestration contracts for workstation stacks."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Mapping, Sequence, TextIO

import boto3
from botocore.client import BaseClient

from workstation_core.ami_lifecycle import (
    AmiModeConfig,
    is_truthy,
    read_ami_mode_from_env,
    resolve_ami_selection,
)


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
class DeployWorkflowInputs:
    """Inputs required for shared deploy orchestration execution.

    Args:
        environment: Requested environment name.
        stack_dir: CDK app path to run deployment commands from.
        stack_name: CloudFormation stack name for post-deploy checks.
        profile: Optional AWS profile override.
        region: Optional AWS region override.
    """

    environment: str
    stack_dir: str
    stack_name: str
    profile: str | None = None
    region: str | None = None


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


LOGGER = logging.getLogger(__name__)
DEPLOY_COMMAND_TIMEOUT_SECONDS = 45 * 60
POST_DEPLOY_CHECK_TIMEOUT_SECONDS = 5 * 60


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


def load_environment_spec(stack_dir: str) -> object | None:
    """Load ``ENVIRONMENT_SPEC`` from a stack directory when available.

    Args:
        stack_dir: Environment stack directory path.

    Returns:
        Environment spec object when resolvable, otherwise ``None``.
    """
    module_path = Path(stack_dir) / "environment_config.py"
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


def make_ec2_client(profile: str | None, region: str | None) -> BaseClient:
    """Create an EC2 client with optional profile and region overrides."""
    profile_name = profile.strip() if profile and profile.strip() else None
    region_name = region.strip() if region and region.strip() else None
    session = boto3.Session(profile_name=profile_name, region_name=region_name)
    if not session.region_name:
        raise RuntimeError(
            "Unable to resolve AWS region. Set --region, AWS_REGION, AWS_DEFAULT_REGION, or configure profile region."
        )
    return session.client("ec2")


def run_command(command: Sequence[str], cwd: str, timeout_seconds: int | None = None) -> None:
    """Run a subprocess command and raise actionable errors for failures."""
    try:
        subprocess.run(command, check=True, cwd=cwd, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as err:
        LOGGER.error(
            "Command timeout while waiting for completion command=%s cwd=%s timeout_seconds=%s",
            " ".join(command),
            cwd,
            timeout_seconds,
        )
        raise RuntimeError(
            "Timed out while waiting for an AWS/CDK operation to finish. "
            "Check CloudFormation events and rerun when the stack is stable."
        ) from err
    except subprocess.CalledProcessError as err:
        LOGGER.error(
            "Command failed command=%s cwd=%s exit_code=%s",
            " ".join(command),
            cwd,
            err.returncode,
        )
        raise RuntimeError(
            f"Command failed (exit code {err.returncode}): {' '.join(command)}"
        ) from err


def deploy_stack(
    stack_dir: str,
    ami_id: str | None,
    bootstrap_on_restored_ami: bool,
) -> None:
    """Deploy CDK stack with optional AMI and restored-AMI bootstrap context."""
    command: list[str] = ["uv", "run", "cdk", "deploy", "--require-approval", "never"]
    if ami_id:
        command.extend(["-c", f"ami_id={ami_id}"])
        if bootstrap_on_restored_ami:
            command.extend(["-c", "bootstrap_on_restored_ami=true"])
    run_command(
        command,
        cwd=stack_dir,
        timeout_seconds=DEPLOY_COMMAND_TIMEOUT_SECONDS,
    )


def run_post_deploy_check(stack_dir: str, stack_name: str) -> None:
    """Run instance helper after a successful deploy."""
    run_command(
        ["uv", "run", "../scripts/check_instance.py", "--stack-name", stack_name],
        cwd=stack_dir,
        timeout_seconds=POST_DEPLOY_CHECK_TIMEOUT_SECONDS,
    )


def _resolve_region(region_override: str | None, env: Mapping[str, str]) -> str | None:
    """Resolve region from CLI override then environment variables."""
    if region_override is not None:
        return region_override
    region = env.get("AWS_REGION")
    if region is not None:
        return region
    return env.get("AWS_DEFAULT_REGION")


def _resolve_profile(profile_override: str | None, env: Mapping[str, str]) -> str | None:
    """Resolve profile from CLI override then ``AWS_PROFILE``."""
    if profile_override is not None:
        return profile_override
    return env.get("AWS_PROFILE")


def run_deploy_lifecycle(
    inputs: DeployWorkflowInputs,
    env: Mapping[str, str] | None = None,
    input_func: Callable[[str], str] = input,
    out: TextIO = sys.stdout,
) -> int:
    """Run the shared deploy lifecycle orchestration flow.

    Args:
        inputs: Deploy execution inputs.
        env: Optional environment mapping for AMI controls and AWS defaults.
        input_func: Input provider for interactive AMI selection.
        out: Output stream for user-facing status lines.

    Returns:
        Zero status code when orchestration completes.
    """
    environment = env or os.environ
    mode: AmiModeConfig = read_ami_mode_from_env(environment)
    profile = _resolve_profile(inputs.profile, environment)
    region = _resolve_region(inputs.region, environment)

    environment_key = inputs.environment
    environment_spec = load_environment_spec(stack_dir=inputs.stack_dir)
    if environment_spec is not None:
        # Reason: use canonical naming from environment spec when available.
        environment_key = str(environment_spec.environment_key)

    ec2_client = make_ec2_client(profile=profile, region=region)
    selection = resolve_ami_selection(
        ec2_client=ec2_client,
        environment_key=environment_key,
        mode=mode,
        input_func=input_func,
        out=out,
    )
    if not selection.should_deploy:
        return 0

    deploy_stack(
        stack_dir=inputs.stack_dir,
        ami_id=selection.selected_ami_id,
        bootstrap_on_restored_ami=mode.ami_bootstrap,
    )
    run_post_deploy_check(stack_dir=inputs.stack_dir, stack_name=inputs.stack_name)
    return 0
