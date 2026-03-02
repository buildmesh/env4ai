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
