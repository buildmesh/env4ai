"""Environment-level workstation specification and naming helpers."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from typing import Mapping

from workstation_core.config import get_shared_network_config


@dataclass(frozen=True, slots=True)
class AmiSelectorConfig:
    """Default AMI lookup parameters for an environment.

    Args:
        owner: AMI owner account id for ``MachineImage.lookup``.
        name: AMI name glob used by ``MachineImage.lookup``.
        filters: Additional EC2 image lookup filters.
    """

    owner: str
    name: str
    filters: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class EnvironmentSpec:
    """Canonical workstation spec for one environment.

    Args:
        environment_key: Stable key (for example ``gastown`` or ``builder``).
        display_name: Human-facing title-cased name (for example ``Gastown``).
        bootstrap_files: Ordered init script filenames to concatenate.
        default_ami_selector: Default AMI selector configuration.
        subnet_cidr: Environment subnet IPv4 CIDR inside the shared VPC.
        instance_type: EC2 instance type for Spot launch.
        volume_size: Root EBS volume size in GiB.
        spot_price: Spot max price as a string (for example ``"0.1"``).
    """

    environment_key: str
    display_name: str
    bootstrap_files: tuple[str, ...]
    default_ami_selector: AmiSelectorConfig
    subnet_cidr: str
    instance_type: str
    volume_size: int
    spot_price: str
    default_access_mode: str = "ssh"
    allowed_ssh_cidr: str | None = None

    @property
    def stack_name(self) -> str:
        """Return the CloudFormation stack name for this environment."""
        return f"{self.display_name}WorkstationStack"

    @property
    def spot_fleet_logical_id(self) -> str:
        """Return the Spot Fleet logical id for this environment."""
        return f"{self.display_name}SpotFleet"

    @property
    def ami_prefix(self) -> str:
        """Return the AMI name prefix for saved environment images."""
        return f"{self.environment_key}_"

    @property
    def ssh_alias(self) -> str:
        """Return the default SSH config host alias."""
        return f"{self.environment_key}-workstation"

    def construct_id(self, suffix: str) -> str:
        """Return a construct id prefixed by display name.

        Args:
            suffix: Suffix token (for example ``VPC`` or ``RouteTable``).

        Returns:
            Prefixed construct id.
        """
        return f"{self.display_name}{suffix}"

    @property
    def resolved_allowed_ssh_cidr(self) -> str | None:
        """Return the normalized SSH ingress CIDR when one is configured."""
        return _normalize_allowed_ssh_cidr(self.allowed_ssh_cidr)


def _normalize_allowed_ssh_cidr(value: str | None) -> str | None:
    """Normalize an optional SSH ingress source into a canonical IPv4 CIDR.

    Args:
        value: Optional IPv4 address or IPv4 CIDR string.

    Returns:
        Normalized CIDR string or ``None`` when unset.

    Raises:
        ValueError: If the value is not a valid IPv4 address or CIDR block.
    """
    if value is None:
        return None

    candidate = value.strip()
    if not candidate:
        return None

    try:
        if "/" in candidate:
            return str(ipaddress.IPv4Network(candidate, strict=True))
        return f"{ipaddress.IPv4Address(candidate)}/32"
    except ValueError as exc:
        raise ValueError(
            "EnvironmentSpec.allowed_ssh_cidr must be a valid IPv4 address or CIDR block."
        ) from exc


def validate_environment_spec(spec: EnvironmentSpec) -> None:
    """Validate required fields and constraints for an environment spec.

    Args:
        spec: Environment spec to validate.

    Raises:
        ValueError: If any required field is empty or invalid.
    """
    if not spec.environment_key.strip():
        raise ValueError("EnvironmentSpec.environment_key must be non-empty.")
    if not spec.display_name.strip():
        raise ValueError("EnvironmentSpec.display_name must be non-empty.")
    if not spec.bootstrap_files:
        raise ValueError("EnvironmentSpec.bootstrap_files must contain at least one file.")
    if not spec.instance_type.strip():
        raise ValueError("EnvironmentSpec.instance_type must be non-empty.")
    if not spec.subnet_cidr.strip():
        raise ValueError("EnvironmentSpec.subnet_cidr must be non-empty.")
    if spec.volume_size <= 0:
        raise ValueError("EnvironmentSpec.volume_size must be greater than 0.")
    if not spec.spot_price.strip():
        raise ValueError("EnvironmentSpec.spot_price must be non-empty.")
    if spec.default_access_mode not in {"ssh", "ssm", "both"}:
        raise ValueError(
            "EnvironmentSpec.default_access_mode must be one of: ssh, ssm, both."
        )
    _normalize_allowed_ssh_cidr(spec.allowed_ssh_cidr)
    if not spec.default_ami_selector.owner.strip():
        raise ValueError("AmiSelectorConfig.owner must be non-empty.")
    if not spec.default_ami_selector.name.strip():
        raise ValueError("AmiSelectorConfig.name must be non-empty.")
    if not spec.default_ami_selector.filters:
        raise ValueError("AmiSelectorConfig.filters must be non-empty.")

    try:
        subnet_network = ipaddress.IPv4Network(spec.subnet_cidr, strict=True)
    except ValueError as exc:
        raise ValueError("EnvironmentSpec.subnet_cidr must be a valid IPv4 CIDR block.") from exc

    shared_network = ipaddress.IPv4Network(get_shared_network_config().vpc_cidr, strict=True)
    if not subnet_network.subnet_of(shared_network):
        raise ValueError(
            "EnvironmentSpec.subnet_cidr must fit within the shared VPC CIDR "
            f"{shared_network.with_prefixlen}."
        )
