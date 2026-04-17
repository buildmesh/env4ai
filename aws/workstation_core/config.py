"""Core configuration models shared by workstation environments."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CoreConfig:
    """Environment-agnostic core workstation configuration.

    Args:
        environment: Logical environment key (for example ``gastown``).
        region: AWS region where infrastructure is deployed.
        stack_prefix: Prefix used to derive resource stack names.
    """

    environment: str
    region: str
    stack_prefix: str


@dataclass(frozen=True, slots=True)
class SharedNetworkConfig:
    """Canonical configuration for the shared workstation network stack.

    Args:
        stack_name: CloudFormation stack name for the shared network.
        vpc_name: Name tag applied to the shared VPC.
        igw_name: Name tag applied to the shared Internet Gateway.
        vpc_cidr: IPv4 CIDR block allocated to the shared VPC.
    """

    stack_name: str
    vpc_name: str
    igw_name: str
    vpc_cidr: str


_SHARED_NETWORK_CONFIG = SharedNetworkConfig(
    stack_name="Env4aiNetworkStack",
    vpc_name="env4ai",
    igw_name="env4ai",
    vpc_cidr="10.0.0.0/16",
)


def get_shared_network_config() -> SharedNetworkConfig:
    """Return the canonical shared network configuration."""
    return _SHARED_NETWORK_CONFIG


def get_shared_network_export_name(output_name: str) -> str:
    """Return the stable CloudFormation export name for a shared-network output."""
    normalized_output_name = output_name.strip()
    if not normalized_output_name:
        raise ValueError("output_name must be non-empty.")
    return f"{_SHARED_NETWORK_CONFIG.stack_name}:{normalized_output_name}"


def validate_config(config: CoreConfig) -> None:
    """Validate a ``CoreConfig`` for required non-empty fields.

    Args:
        config: Configuration object to validate.

    Raises:
        ValueError: If any required field is empty after trimming.
    """
    if not config.environment.strip():
        raise ValueError("CoreConfig.environment must be non-empty.")
    if not config.region.strip():
        raise ValueError("CoreConfig.region must be non-empty.")
    if not config.stack_prefix.strip():
        raise ValueError("CoreConfig.stack_prefix must be non-empty.")
