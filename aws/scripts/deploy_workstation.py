#!/usr/bin/env python3
"""Deploy workstation stacks via shared workstation_core orchestration."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

# Reason: allow importing sibling shared package when executed as a script.
AWS_ROOT = Path(__file__).resolve().parents[1]
if str(AWS_ROOT) not in sys.path:
    sys.path.insert(0, str(AWS_ROOT))

from workstation_core.orchestration import DeployWorkflowInputs, run_deploy_lifecycle


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


def main(argv: Sequence[str] | None = None) -> int:
    """Run deploy orchestration flow and return process status code."""
    args = parse_args(argv)
    return run_deploy_lifecycle(
        DeployWorkflowInputs(
            environment=args.environment,
            stack_dir=args.stack_dir,
            stack_name=args.stack_name,
            profile=args.profile,
            region=args.region,
        )
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        raise SystemExit(1)
