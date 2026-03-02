"""Shared workstation core package.

This package defines cross-environment foundations that can be reused by
multiple AWS workstation applications.
"""

from workstation_core.cdk_helpers import (
    CdkTarget,
    build_bootstrap_user_data,
    build_spot_fleet_launch_specification,
    build_stack_name,
    resolve_ami_id,
    resolve_subnet_availability_zone,
)
from workstation_core.config import CoreConfig
from workstation_core.environment_config import (
    AmiSelectorConfig,
    EnvironmentSpec,
    validate_environment_spec,
)
from workstation_core.orchestration import OrchestrationPlan, validate_plan
from workstation_core.runtime import RuntimeContext
from workstation_core.runtime_resolution import (
    get_account,
    get_profile_name,
    get_profile_section_name,
    get_region,
    get_region_from_config,
    load_aws_config,
    parse_optional_bool_context,
    parse_optional_text_context,
)

__all__ = [
    "AmiSelectorConfig",
    "CdkTarget",
    "CoreConfig",
    "EnvironmentSpec",
    "OrchestrationPlan",
    "RuntimeContext",
    "build_bootstrap_user_data",
    "build_spot_fleet_launch_specification",
    "build_stack_name",
    "resolve_ami_id",
    "resolve_subnet_availability_zone",
    "validate_environment_spec",
    "validate_plan",
    "get_account",
    "get_profile_name",
    "get_profile_section_name",
    "get_region",
    "get_region_from_config",
    "load_aws_config",
    "parse_optional_bool_context",
    "parse_optional_text_context",
]
