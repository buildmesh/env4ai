"""Shared workstation core package.

This package defines cross-environment foundations that can be reused by
multiple AWS workstation applications.
"""

from workstation_core.cdk_helpers import CdkTarget, build_stack_name
from workstation_core.config import CoreConfig
from workstation_core.orchestration import OrchestrationPlan, validate_plan
from workstation_core.runtime import RuntimeContext

__all__ = [
    "CdkTarget",
    "CoreConfig",
    "OrchestrationPlan",
    "RuntimeContext",
    "build_stack_name",
    "validate_plan",
]
