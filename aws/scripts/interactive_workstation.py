#!/usr/bin/env python3
"""Interactive workstation lifecycle menu."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Sequence

import boto3

# Reason: allow importing sibling shared package when executed as a script.
AWS_ROOT = Path(__file__).resolve().parents[1]
if str(AWS_ROOT) not in sys.path:
    sys.path.insert(0, str(AWS_ROOT))

from workstation_core.interactive_workstation import (
    ActionResult,
    EnvironmentTarget,
    choose_environment,
    discover_environments,
    dispatch_action,
    load_last_used_environment_key,
    parse_action_choice,
    run_script,
    save_last_used_environment_key,
)
from workstation_core.workstation_status import WorkstationStatus, get_workstation_status


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line args for interactive workstation mode."""
    parser = argparse.ArgumentParser(description="Run interactive workstation lifecycle UI.")
    parser.add_argument(
        "--aws-root",
        default=str(AWS_ROOT),
        help="AWS root directory containing environment subdirectories.",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Optional AWS profile override.",
    )
    parser.add_argument(
        "--region",
        default=None,
        help="Optional AWS region override.",
    )
    parser.add_argument(
        "--state-file",
        default=str(Path.home() / ".config" / "env4ai" / "workstation-last-environment"),
        help="Path used to persist the last selected environment key.",
    )
    return parser.parse_args(argv)


def _resolve_region(cli_region: str | None) -> str | None:
    """Resolve region precedence from CLI then AWS env vars."""
    if cli_region and cli_region.strip():
        return cli_region.strip()
    if os.environ.get("AWS_REGION", "").strip():
        return os.environ["AWS_REGION"].strip()
    if os.environ.get("AWS_DEFAULT_REGION", "").strip():
        return os.environ["AWS_DEFAULT_REGION"].strip()
    return None


def _resolve_profile(cli_profile: str | None) -> str | None:
    """Resolve profile precedence from CLI then AWS env vars."""
    if cli_profile and cli_profile.strip():
        return cli_profile.strip()
    if os.environ.get("AWS_PROFILE", "").strip():
        return os.environ["AWS_PROFILE"].strip()
    return None


def _render_status(environment: EnvironmentTarget, status: WorkstationStatus) -> None:
    """Render concise status details for the selected environment."""
    print("\nEnvironment status:")
    print(f"  Environment: {environment.display_name} [{environment.environment_key}]")
    print(f"  Stack state: {status.stack_state}")
    if status.stack_status:
        print(f"  Stack status: {status.stack_status}")
    if status.stack_state == "running":
        if status.instance_id:
            print(f"  Instance ID: {status.instance_id}")
        if status.public_ip:
            print(f"  Public IP: {status.public_ip}")
        if status.ssh_alias:
            print(f"  SSH alias: {status.ssh_alias}")


def _show_action_menu() -> None:
    """Print available action options."""
    print("\nActions:")
    print("  1. Deploy with default AMI")
    print("  2. Deploy with AMI list + pick")
    print("  3. Save current state as AMI")
    print("  4. Destroy stack")
    print("  5. Destroy stack + save AMI first")
    print("  6. Refresh status")
    print("  7. Switch environment")
    print("  8. Quit")


def _run_action_loop(
    *,
    environment: EnvironmentTarget,
    cloudformation_client: object,
    ec2_client: object,
) -> ActionResult:
    """Run actions loop for one selected environment."""
    while True:
        status = get_workstation_status(
            cloudformation_client,
            ec2_client,
            stack_name=environment.stack_name,
            spot_fleet_logical_id=environment.spot_fleet_logical_id,
            ssh_alias=environment.ssh_alias,
        )
        _render_status(environment, status)
        _show_action_menu()
        choice = parse_action_choice(input("Choose action (1-8): "))
        if choice is None:
            print("Invalid selection. Enter 1-8, or q to quit.")
            continue
        try:
            result = dispatch_action(
                choice,
                environment,
                input_func=input,
                out=sys.stdout,
                runner=lambda command, cwd, env_overrides: run_script(
                    command,
                    cwd=cwd,
                    env_overrides=env_overrides,
                ),
            )
        except RuntimeError as err:
            print(str(err))
            continue
        if result.switch_environment or result.should_quit:
            return result


def main(argv: Sequence[str] | None = None) -> int:
    """Run interactive environment selection and lifecycle actions."""
    args = parse_args(argv)
    aws_root = Path(args.aws_root).resolve()
    state_file = Path(args.state_file)

    profile = _resolve_profile(args.profile)
    region = _resolve_region(args.region)
    session = boto3.Session(profile_name=profile, region_name=region)
    if not session.region_name:
        raise RuntimeError(
            "Unable to resolve AWS region. Set --region, AWS_REGION, AWS_DEFAULT_REGION, or configure profile region."
        )

    cloudformation_client = session.client("cloudformation")
    ec2_client = session.client("ec2")
    environments = discover_environments(aws_root, out=sys.stdout)
    last_used_environment_key = load_last_used_environment_key(state_file)

    while True:
        selected = choose_environment(
            environments,
            input_func=input,
            out=sys.stdout,
            last_used_environment_key=last_used_environment_key,
        )
        if selected is None:
            print("Bye.")
            return 0

        save_last_used_environment_key(state_file, selected.environment_key)
        last_used_environment_key = selected.environment_key
        result = _run_action_loop(
            environment=selected,
            cloudformation_client=cloudformation_client,
            ec2_client=ec2_client,
        )
        if result.should_quit:
            print("Bye.")
            return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        raise SystemExit(1)
