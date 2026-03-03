#!/usr/bin/env python3
"""Save a workstation instance as an AMI without destroying the stack."""

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

from workstation_core import (
    build_stop_image_name,
    create_image_from_instance,
    load_environment_spec,
    resolve_running_instance_id,
    wait_for_image_available,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI args for save-only workflow."""
    parser = argparse.ArgumentParser(
        description="Save an AMI from the currently running workstation instance."
    )
    parser.add_argument(
        "--environment",
        required=True,
        help="Environment key used in AMI naming (<environment>_<tag>).",
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
        help="Optional Spot Fleet logical id override.",
    )
    parser.add_argument(
        "--ami-tag",
        required=True,
        help="AMI tag suffix for saved image name (<environment>_<tag>).",
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
    """Run save-only AMI workflow."""
    args = parse_args(argv)
    profile = _resolve_profile(args.profile)
    region = _resolve_region(args.region)

    session = boto3.Session(profile_name=profile, region_name=region)
    if not session.region_name:
        raise RuntimeError(
            "Unable to resolve AWS region. Set --region, AWS_REGION, AWS_DEFAULT_REGION, or configure profile region."
        )

    environment_key = _resolve_environment_key(
        stack_dir=args.stack_dir,
        fallback_environment=args.environment,
    )
    image_name = build_stop_image_name(environment_key, args.ami_tag)
    spot_fleet_logical_id = _resolve_spot_fleet_logical_id(args)

    ec2_client = session.client("ec2")
    cloudformation_client = session.client("cloudformation")
    instance_id = resolve_running_instance_id(
        cloudformation_client,
        ec2_client,
        stack_name=args.stack_name,
        spot_fleet_logical_id=spot_fleet_logical_id,
    )
    image_id = create_image_from_instance(
        ec2_client,
        instance_id=instance_id,
        image_name=image_name,
    )
    wait_for_image_available(ec2_client, image_id=image_id)
    print(f"Saved AMI {image_name} ({image_id})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        raise SystemExit(1)
