"""Canonical environment specification for the openclaw workstation."""

from workstation_core import AmiSelectorConfig, EnvironmentSpec, validate_environment_spec

_ENVIRONMENT_SPEC = EnvironmentSpec(
    environment_key="openclaw",
    display_name="OpenClaw",
    bootstrap_files=(
        "deps.sh",
        "agents.sh",
        "docker.sh",
        "openclaw.sh",
    ),
    default_ami_selector=AmiSelectorConfig(
        owner="099720109477",
        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
        filters={"architecture": ("x86_64",)},
    ),
    instance_type="t3.large",
    volume_size=30,
    spot_price="0.1",
)
validate_environment_spec(_ENVIRONMENT_SPEC)

ENVIRONMENT_SPEC = _ENVIRONMENT_SPEC
