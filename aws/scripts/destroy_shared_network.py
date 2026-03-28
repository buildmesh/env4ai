#!/usr/bin/env python3
"""Destroy the shared env4ai network stack after preflight checks."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

AWS_ROOT = Path(__file__).resolve().parents[1]
if str(AWS_ROOT) not in sys.path:
    sys.path.insert(0, str(AWS_ROOT))

from workstation_core.orchestration import destroy_shared_network_stack


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for shared-network destroy."""
    parser = argparse.ArgumentParser(
        description=(
            "Destroy Env4aiNetworkStack after confirming no environment workstation stacks remain."
        )
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
    """Run shared-network destroy orchestration."""
    args = parse_args(argv)
    return destroy_shared_network_stack(profile=args.profile, region=args.region)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        raise SystemExit(1)
