"""Interactive workstation UX helpers shared by CLI entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import subprocess
from typing import Callable, TextIO


@dataclass(frozen=True, slots=True)
class EnvironmentTarget:
    """Environment metadata required by interactive lifecycle actions.

    Args:
        environment_key: Canonical environment key.
        display_name: Human-friendly environment name.
        stack_dir: Absolute path to environment stack directory.
        stack_name: CloudFormation stack name.
        spot_fleet_logical_id: Spot Fleet logical resource id.
        ssh_alias: SSH host alias for the environment.
    """

    environment_key: str
    display_name: str
    stack_dir: Path
    stack_name: str
    spot_fleet_logical_id: str
    ssh_alias: str


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Action dispatch outcome.

    Args:
        switch_environment: Whether caller should return to environment picker.
        should_quit: Whether caller should exit interactive loop.
    """

    switch_environment: bool = False
    should_quit: bool = False


@dataclass(frozen=True, slots=True)
class InteractiveEnvironmentState:
    """Runtime state used to gate interactive actions.

    Args:
        stack_state: High-level stack state shown in the interactive UI.
        stack_status: Raw CloudFormation stack status, when available.
        is_deployed: Whether stack exists and is not terminally deleted.
    """

    stack_state: str
    stack_status: str | None
    is_deployed: bool


@dataclass(frozen=True, slots=True)
class ActionAvailability:
    """Availability information for one action menu entry.

    Args:
        enabled: Whether the action can execute right now.
        disabled_reason: User-facing reason when action is disabled.
    """

    enabled: bool
    disabled_reason: str | None = None


DEPLOY_DISABLED_REASON = "Unavailable: stack is already deployed."
REQUIRES_DEPLOYED_REASON = "Unavailable: deploy the stack first."
TERMINAL_DELETED_STACK_STATUSES: frozenset[str] = frozenset({"DELETE_COMPLETE"})


def _load_environment_spec(directory: Path) -> object | None:
    """Load ``ENVIRONMENT_SPEC`` from an environment directory when available."""
    module_path = directory / "environment_config.py"
    if not module_path.is_file():
        return None

    import_spec = importlib.util.spec_from_file_location(
        f"interactive_environment_config_{directory.name}",
        str(module_path),
    )
    if import_spec is None or import_spec.loader is None:
        return None
    module = importlib.util.module_from_spec(import_spec)
    import_spec.loader.exec_module(module)
    return getattr(module, "ENVIRONMENT_SPEC", None)


def discover_environments(aws_root: Path, out: TextIO) -> list[EnvironmentTarget]:
    """Discover valid environments from immediate subdirectories of ``aws_root``.

    Args:
        aws_root: Path that contains environment directories.
        out: Stream used for non-fatal warnings.

    Returns:
        Sorted list of discovered environment metadata.

    Raises:
        RuntimeError: If no valid environment specs are discovered.
    """
    discovered: list[EnvironmentTarget] = []
    for child in sorted(aws_root.iterdir(), key=lambda entry: entry.name.lower()):
        if not child.is_dir():
            continue

        try:
            environment_spec = _load_environment_spec(child)
        except Exception as err:
            out.write(f"Warning: skipping '{child.name}' (invalid environment config: {err})\n")
            continue

        if environment_spec is None:
            continue

        try:
            environment_key = str(environment_spec.environment_key).strip()
            display_name = str(environment_spec.display_name).strip()
            stack_name = str(environment_spec.stack_name).strip()
            spot_fleet_logical_id = str(environment_spec.spot_fleet_logical_id).strip()
            ssh_alias = str(environment_spec.ssh_alias).strip()
        except Exception as err:
            out.write(f"Warning: skipping '{child.name}' (malformed environment spec: {err})\n")
            continue

        if not all(
            [
                environment_key,
                display_name,
                stack_name,
                spot_fleet_logical_id,
                ssh_alias,
            ]
        ):
            out.write(f"Warning: skipping '{child.name}' (missing required environment fields)\n")
            continue

        discovered.append(
            EnvironmentTarget(
                environment_key=environment_key,
                display_name=display_name,
                stack_dir=child.resolve(),
                stack_name=stack_name,
                spot_fleet_logical_id=spot_fleet_logical_id,
                ssh_alias=ssh_alias,
            )
        )

    if not discovered:
        raise RuntimeError(
            f"No valid environments discovered under '{aws_root}'. "
            "Add aws/<env>/environment_config.py with a valid ENVIRONMENT_SPEC."
        )

    return sorted(
        discovered,
        key=lambda environment: (environment.display_name.lower(), environment.environment_key.lower()),
    )


def _build_alias_map(environments: list[EnvironmentTarget]) -> dict[str, EnvironmentTarget]:
    """Build an unambiguous alias map for short environment selection."""
    alias_candidates: dict[str, list[EnvironmentTarget]] = {}
    for environment in environments:
        base_tokens = {
            environment.environment_key.lower(),
            environment.display_name.lower().replace(" ", ""),
            environment.stack_dir.name.lower(),
        }
        for token in base_tokens:
            if len(token) < 2:
                continue
            for size in range(2, len(token) + 1):
                alias = token[:size]
                alias_candidates.setdefault(alias, []).append(environment)

    alias_map: dict[str, EnvironmentTarget] = {}
    for alias, targets in alias_candidates.items():
        unique_targets = {item.environment_key: item for item in targets}
        if len(unique_targets) == 1:
            alias_map[alias] = next(iter(unique_targets.values()))
    return alias_map


def choose_environment(
    environments: list[EnvironmentTarget],
    *,
    input_func: Callable[[str], str],
    out: TextIO,
    last_used_environment_key: str | None,
) -> EnvironmentTarget | None:
    """Prompt for an environment selection.

    Args:
        environments: Discovered environments.
        input_func: User input callback.
        out: Stream for user prompts.
        last_used_environment_key: Most recently selected environment key.

    Returns:
        Selected environment or ``None`` when user chooses to quit.
    """
    alias_map = _build_alias_map(environments)
    by_key = {environment.environment_key.lower(): environment for environment in environments}
    by_name = {environment.display_name.lower(): environment for environment in environments}
    by_directory = {environment.stack_dir.name.lower(): environment for environment in environments}

    while True:
        out.write("\nSelect environment:\n")
        for index, environment in enumerate(environments, start=1):
            marker = ""
            if (
                last_used_environment_key is not None
                and environment.environment_key == last_used_environment_key
            ):
                marker = " (last used)"
            out.write(f"  {index}. {environment.display_name} [{environment.environment_key}]{marker}\n")
        out.write("Input: number, key/name/alias, Enter for last-used, or q to quit.\n")
        selection = input_func("> ").strip()
        normalized = selection.lower()

        if normalized == "q":
            return None

        if not normalized:
            if last_used_environment_key is None:
                out.write("No last-used environment saved yet. Please pick an option.\n")
                continue
            last_used = by_key.get(last_used_environment_key.lower())
            if last_used is None:
                out.write(
                    f"Saved environment '{last_used_environment_key}' is unavailable. Please pick another option.\n"
                )
                continue
            return last_used

        if normalized.isdigit():
            index = int(normalized)
            if 1 <= index <= len(environments):
                return environments[index - 1]
            out.write(f"Invalid index '{selection}'. Enter 1-{len(environments)}.\n")
            continue

        if normalized in by_key:
            return by_key[normalized]
        if normalized in by_name:
            return by_name[normalized]
        if normalized in by_directory:
            return by_directory[normalized]
        if normalized in alias_map:
            return alias_map[normalized]

        out.write(
            f"Unrecognized environment '{selection}'. Use a number, key/name/alias, Enter, or q.\n"
        )


def load_last_used_environment_key(state_file: Path) -> str | None:
    """Load the last-used environment key from disk when available."""
    try:
        value = state_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def save_last_used_environment_key(state_file: Path, environment_key: str) -> None:
    """Persist the last-used environment key to disk."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(f"{environment_key}\n", encoding="utf-8")


def parse_action_choice(input_value: str) -> str | None:
    """Normalize action menu input into a canonical action token."""
    normalized = input_value.strip().lower()
    mapping = {
        "1": "deploy_default",
        "2": "deploy_pick_ami",
        "3": "save_ami_only",
        "4": "destroy",
        "5": "destroy_and_save",
        "6": "refresh",
        "7": "switch_environment",
        "8": "quit",
        "d": "deploy_default",
        "p": "deploy_pick_ami",
        "s": "save_ami_only",
        "x": "destroy",
        "dx": "destroy_and_save",
        "r": "refresh",
        "w": "switch_environment",
        "q": "quit",
    }
    return mapping.get(normalized)


def derive_is_deployed(*, stack_state: str, stack_status: str | None) -> bool:
    """Derive deployment state from workstation stack metadata.

    Args:
        stack_state: High-level stack state from status helper.
        stack_status: Raw CloudFormation stack status.

    Returns:
        ``True`` when stack exists and is not terminally deleted.
    """
    if stack_state.strip().lower() == "not found":
        return False
    normalized_status = (stack_status or "").strip().upper()
    return normalized_status not in TERMINAL_DELETED_STACK_STATUSES


def build_action_availability(
    state: InteractiveEnvironmentState,
) -> dict[str, ActionAvailability]:
    """Compute action availability for one interactive render/execute cycle.

    Args:
        state: Derived environment state for policy checks.

    Returns:
        Mapping of canonical action key -> availability metadata.
    """
    deploy_enabled = not state.is_deployed
    requires_deployed_enabled = state.is_deployed
    return {
        "deploy_default": ActionAvailability(
            enabled=deploy_enabled,
            disabled_reason=None if deploy_enabled else DEPLOY_DISABLED_REASON,
        ),
        "deploy_pick_ami": ActionAvailability(
            enabled=deploy_enabled,
            disabled_reason=None if deploy_enabled else DEPLOY_DISABLED_REASON,
        ),
        "save_ami_only": ActionAvailability(
            enabled=requires_deployed_enabled,
            disabled_reason=None if requires_deployed_enabled else REQUIRES_DEPLOYED_REASON,
        ),
        "destroy": ActionAvailability(
            enabled=requires_deployed_enabled,
            disabled_reason=None if requires_deployed_enabled else REQUIRES_DEPLOYED_REASON,
        ),
        "destroy_and_save": ActionAvailability(
            enabled=requires_deployed_enabled,
            disabled_reason=None if requires_deployed_enabled else REQUIRES_DEPLOYED_REASON,
        ),
        "refresh": ActionAvailability(enabled=True),
        "switch_environment": ActionAvailability(enabled=True),
        "quit": ActionAvailability(enabled=True),
    }


def run_script(
    command: list[str],
    *,
    cwd: Path,
    env_overrides: dict[str, str] | None = None,
) -> None:
    """Run a command and raise actionable runtime errors on failure."""
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    try:
        subprocess.run(command, check=True, cwd=str(cwd), env=env)
    except subprocess.CalledProcessError as err:
        raise RuntimeError(
            f"Command failed (exit code {err.returncode}): {' '.join(command)}"
        ) from err


def _prompt_ami_tag(*, input_func: Callable[[str], str], out: TextIO) -> str:
    """Prompt for an AMI tag with retry behavior and quit support."""
    while True:
        value = input_func("AMI tag (or q to cancel): ").strip()
        if value.lower() == "q":
            raise RuntimeError("AMI save canceled by user.")
        if value:
            return value
        out.write("AMI tag is required.\n")


def _confirm_exact_yes(
    *,
    prompt: str,
    cancellation_message: str,
    input_func: Callable[[str], str],
    out: TextIO,
) -> bool:
    """Require an exact ``yes`` confirmation for destructive actions.

    Args:
        prompt: Prompt text that asks for confirmation.
        cancellation_message: Message shown when user does not type ``yes``.
        input_func: Input callback.
        out: Output stream.

    Returns:
        ``True`` when user typed exact ``yes``.
    """
    response = input_func(prompt).strip()
    if response == "yes":
        return True
    out.write(f"{cancellation_message}\n")
    return False


def dispatch_action(
    action: str,
    environment: EnvironmentTarget,
    *,
    input_func: Callable[[str], str],
    out: TextIO,
    runner: Callable[[list[str], Path, dict[str, str] | None], None],
) -> ActionResult:
    """Dispatch one interactive action.

    Args:
        action: Canonical action key from ``parse_action_choice``.
        environment: Selected environment metadata.
        input_func: User input callback.
        out: Stream for user-facing messages.
        runner: Command runner callback.

    Returns:
        Action result with loop-control flags.
    """
    deploy_command = [
        "uv",
        "run",
        "../scripts/deploy_workstation.py",
        "--environment",
        environment.environment_key,
        "--stack-dir",
        str(environment.stack_dir),
        "--stack-name",
        environment.stack_name,
    ]
    stop_command = [
        "uv",
        "run",
        "../scripts/stop_workstation.py",
        "--environment",
        environment.environment_key,
        "--stack-dir",
        str(environment.stack_dir),
        "--stack-name",
        environment.stack_name,
        "--spot-fleet-logical-id",
        environment.spot_fleet_logical_id,
    ]

    if action == "deploy_default":
        runner(deploy_command, environment.stack_dir, None)
        return ActionResult()

    if action == "deploy_pick_ami":
        runner(
            deploy_command,
            environment.stack_dir,
            {"AMI_LIST": "1", "AMI_PICK": "1"},
        )
        return ActionResult()

    if action == "save_ami_only":
        ami_tag = _prompt_ami_tag(input_func=input_func, out=out)
        runner(
            [
                "uv",
                "run",
                "../scripts/save_workstation_ami.py",
                "--environment",
                environment.environment_key,
                "--stack-dir",
                str(environment.stack_dir),
                "--stack-name",
                environment.stack_name,
                "--spot-fleet-logical-id",
                environment.spot_fleet_logical_id,
                "--ami-tag",
                ami_tag,
            ],
            environment.stack_dir,
            None,
        )
        return ActionResult()

    if action == "destroy":
        if not _confirm_exact_yes(
            prompt="Type 'yes' to destroy stack: ",
            cancellation_message="Destroy canceled.",
            input_func=input_func,
            out=out,
        ):
            return ActionResult()
        runner(stop_command, environment.stack_dir, None)
        return ActionResult()

    if action == "destroy_and_save":
        ami_tag = _prompt_ami_tag(input_func=input_func, out=out)
        out.write(
            "Destroy + save summary:\n"
            f"  environment: {environment.environment_key}\n"
            f"  ami_tag: {ami_tag}\n"
            "  action: save AMI, then destroy stack\n"
        )
        if not _confirm_exact_yes(
            prompt="Type 'yes' to continue: ",
            cancellation_message="Destroy + save canceled.",
            input_func=input_func,
            out=out,
        ):
            return ActionResult()
        runner(stop_command, environment.stack_dir, {"AMI_SAVE": "1", "AMI_TAG": ami_tag})
        return ActionResult()

    if action == "refresh":
        return ActionResult()

    if action == "switch_environment":
        return ActionResult(switch_environment=True)

    if action == "quit":
        return ActionResult(should_quit=True)

    raise RuntimeError(f"Unknown action: {action}")
