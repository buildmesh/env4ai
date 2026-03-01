#!/usr/bin/env python3
"""Deploy workstation stacks with optional AMI load/list/pick behavior."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Callable, Sequence, TextIO

import boto3
from botocore.client import BaseClient


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: Optional CLI arguments for testability.

    Returns:
        Parsed namespace with deploy configuration.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Deploy a workstation CDK stack with optional AMI load/list/pick "
            "controls from AMI_LOAD, AMI_LIST, and AMI_PICK."
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
        help="CloudFormation stack name used by check_instance helper.",
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


def is_truthy(value: str | None) -> bool:
    """Interpret common truthy string values."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


def make_ec2_client(profile: str | None, region: str | None) -> BaseClient:
    """Create an EC2 client with optional profile/region overrides."""
    profile_name = profile.strip() if profile and profile.strip() else None
    region_name = region.strip() if region and region.strip() else None
    session = boto3.Session(profile_name=profile_name, region_name=region_name)
    if not session.region_name:
        raise RuntimeError(
            "Unable to resolve AWS region. Set --region, AWS_REGION, AWS_DEFAULT_REGION, or configure profile region."
        )
    return session.client("ec2")


def list_environment_images(ec2_client: BaseClient, environment: str) -> list[dict[str, str]]:
    """List AMIs matching ``<environment>_*`` with key metadata.

    Args:
        ec2_client: Boto3 EC2 client.
        environment: Environment prefix in AMI names.

    Returns:
        Sorted AMI records (newest first).
    """
    pattern = f"{environment}_*"
    response = ec2_client.describe_images(
        Owners=["self"],
        Filters=[{"Name": "name", "Values": [pattern]}],
    )
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
    """Resolve AMI ID by exact AMI name.

    Args:
        ec2_client: Boto3 EC2 client.
        expected_name: Exact expected AMI name.

    Returns:
        Matched AMI ID.

    Raises:
        RuntimeError: If no exact match exists.
    """
    response = ec2_client.describe_images(
        Owners=["self"],
        Filters=[{"Name": "name", "Values": [expected_name]}],
    )
    candidates = response.get("Images", [])
    exact_matches = [
        image
        for image in candidates
        if str(image.get("Name", "")) == expected_name
    ]
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


def run_command(command: Sequence[str], cwd: str) -> None:
    """Run a subprocess command and fail on non-zero exit."""
    subprocess.run(command, check=True, cwd=cwd)


def deploy_stack(stack_dir: str, ami_id: str | None) -> None:
    """Deploy CDK stack, optionally passing an AMI override context."""
    command: list[str] = ["uv", "run", "cdk", "deploy", "--require-approval", "never"]
    if ami_id:
        command.extend(["-c", f"ami_id={ami_id}"])
    run_command(command, cwd=stack_dir)


def run_post_deploy_check(stack_dir: str, stack_name: str) -> None:
    """Run the existing instance helper after successful deploy."""
    run_command(
        ["uv", "run", "../scripts/check_instance.py", "--stack-name", stack_name],
        cwd=stack_dir,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run deploy orchestration flow and return process status code."""
    args = parse_args(argv)
    ami_load_tag = os.environ.get("AMI_LOAD", "").strip()
    ami_list = is_truthy(os.environ.get("AMI_LIST"))
    ami_pick = is_truthy(os.environ.get("AMI_PICK"))

    validate_mode_arguments(
        ami_load_tag=ami_load_tag,
        ami_list=ami_list,
        ami_pick=ami_pick,
    )

    selected_ami_id: str | None = None
    profile = args.profile if args.profile is not None else os.environ.get("AWS_PROFILE")
    region = args.region if args.region is not None else os.environ.get("AWS_REGION")
    if region is None:
        region = os.environ.get("AWS_DEFAULT_REGION")

    ec2_client = make_ec2_client(profile=profile, region=region)

    if ami_load_tag:
        expected_name = f"{args.environment}_{ami_load_tag}"
        selected_ami_id = resolve_exact_image_id(ec2_client, expected_name=expected_name)
        print(f"Resolved AMI {expected_name} -> {selected_ami_id}")
    elif ami_list:
        images = list_environment_images(ec2_client, environment=args.environment)
        print_image_list(images)
        if not ami_pick:
            return 0
        selected_image = pick_image_interactively(images)
        selected_ami_id = selected_image["image_id"]
        print(
            f"Selected AMI {selected_image['name']} "
            f"({selected_image['image_id']}) for deploy."
        )

    deploy_stack(stack_dir=args.stack_dir, ami_id=selected_ami_id)
    run_post_deploy_check(stack_dir=args.stack_dir, stack_name=args.stack_name)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as err:
        print(f"Command failed with exit code {err.returncode}: {' '.join(err.cmd)}", file=sys.stderr)
        raise SystemExit(err.returncode)
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        raise SystemExit(1)
