#!/usr/bin/env python3
"""Stop workstation stacks with optional AMI save-on-stop behavior."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Sequence

import boto3

from deploy_workstation import load_environment_spec, run_command
from workstation_core import (
    StopOrchestrationInputs,
    build_stop_image_name,
    create_image_from_instance,
    parse_stop_ami_config,
    resolve_running_instance_id,
    run_stop_orchestration,
    wait_for_image_available,
)

DESTROY_TIMEOUT_SECONDS = 45 * 60


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for stop workflow."""
    parser = argparse.ArgumentParser(
        description=(
            "Destroy a workstation stack. When AMI_SAVE=1 and AMI_TAG is set, "
            "save an AMI from the running instance before destroy."
        )
    )
    parser.add_argument(
        "--environment",
        required=True,
        help="Environment name used in AMI naming (<environment>_<tag>).",
    )
    parser.add_argument(
        "--stack-dir",
        required=True,
        help="Path to CDK app directory (for example: aws/gastown).",
    )
    parser.add_argument(
        "--stack-name",
        required=True,
        help="CloudFormation stack name.",
    )
    parser.add_argument(
        "--spot-fleet-logical-id",
        default=None,
        help="Optional stack Spot Fleet logical id override.",
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


def _resolve_environment_key(stack_dir: str, fallback_environment: str) -> str:
    """Resolve canonical environment key from environment spec when available."""
    environment_spec = load_environment_spec(stack_dir=stack_dir)
    if environment_spec is None:
        return fallback_environment
    # Reason: prefer canonical environment key when stack naming differs by display name.
    return str(environment_spec.environment_key)


def _resolve_spot_fleet_logical_id(args: argparse.Namespace) -> str:
    """Resolve Spot Fleet logical id from CLI or environment spec defaults."""
    if args.spot_fleet_logical_id and args.spot_fleet_logical_id.strip():
        return args.spot_fleet_logical_id.strip()

    environment_spec = load_environment_spec(stack_dir=args.stack_dir)
    if environment_spec is not None:
        return str(environment_spec.spot_fleet_logical_id)

    return f"{Path(args.stack_dir).name.capitalize()}SpotFleet"


def main(argv: Sequence[str] | None = None) -> int:
    """Run stop workflow with optional save-on-stop AMI path."""
    args = parse_args(argv)
    ami_save, ami_tag = parse_stop_ami_config(os.environ)

    profile = _resolve_profile(args.profile)
    region = _resolve_region(args.region)
    session = boto3.Session(profile_name=profile, region_name=region)
    if not session.region_name:
        raise RuntimeError(
            "Unable to resolve AWS region. Set --region, AWS_REGION, AWS_DEFAULT_REGION, or configure profile region."
        )

    ec2_client = session.client("ec2")
    cloudformation_client = session.client("cloudformation")
    environment_key = _resolve_environment_key(
        stack_dir=args.stack_dir,
        fallback_environment=args.environment,
    )
    spot_fleet_logical_id = _resolve_spot_fleet_logical_id(args)
    stop_inputs = StopOrchestrationInputs(
        environment_key=environment_key,
        stack_name=args.stack_name,
        spot_fleet_logical_id=spot_fleet_logical_id,
        ami_save=ami_save,
        ami_tag=ami_tag,
    )

    saved_image_id = run_stop_orchestration(
        stop_inputs,
        resolve_running_instance_id=lambda: resolve_running_instance_id(
            cloudformation_client,
            ec2_client,
            stack_name=args.stack_name,
            spot_fleet_logical_id=spot_fleet_logical_id,
        ),
        create_image=lambda instance_id, image_name: create_image_from_instance(
            ec2_client,
            instance_id=instance_id,
            image_name=image_name,
        ),
        wait_for_image_available=lambda image_id: wait_for_image_available(
            ec2_client,
            image_id=image_id,
        ),
        destroy_stack=lambda: run_command(
            ["uv", "run", "cdk", "destroy", "--force"],
            cwd=args.stack_dir,
            timeout_seconds=DESTROY_TIMEOUT_SECONDS,
        ),
    )

    if saved_image_id is not None:
        image_name = build_stop_image_name(environment_key, ami_tag or "")
        print(f"Saved AMI {image_name} ({saved_image_id})")
    print("Destroy complete.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        raise SystemExit(1)
