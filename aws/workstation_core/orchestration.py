"""Shared orchestration contracts for workstation workflows."""

from dataclasses import dataclass


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
