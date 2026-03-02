"""Utilities for shared CDK naming and target derivation."""

from dataclasses import dataclass


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
