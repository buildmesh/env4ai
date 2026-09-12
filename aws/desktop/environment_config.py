"""Canonical environment specification for the gastown workstation."""

from workstation_core import AmiSelectorConfig, EnvironmentSpec, validate_environment_spec

_ENVIRONMENT_SPEC = EnvironmentSpec(
    environment_key="desktop",
    display_name="Desktop",
    bootstrap_files=(
        "gui.sh",
        "brave.sh",
        "libreoffice.sh",
        "nodejs.sh",
        "agents.sh",
    ),
    default_ami_selector=AmiSelectorConfig(
        owner="099720109477",
        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
        filters={"architecture": ("x86_64",)},
    ),
    subnet_cidr="10.0.4.0/24",
    private_ip_address=None,  # Set an available subnet IPv4 address to pin the internal IP.
    ssh_authorized_keys=(),  # Add public key strings for the ubuntu user's SSH access.
    instance_type="t3.xlarge",
    volume_size=16,
    spot_price="0.1",
    default_access_mode="ssh",
)
validate_environment_spec(_ENVIRONMENT_SPEC)

ENVIRONMENT_SPEC = _ENVIRONMENT_SPEC
