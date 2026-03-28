"""Canonical environment specification for the gastown workstation."""

from workstation_core import AmiSelectorConfig, EnvironmentSpec, validate_environment_spec

_ENVIRONMENT_SPEC = EnvironmentSpec(
    environment_key="codereview",
    display_name="CodeReview",
    bootstrap_files=(
        "deps.sh",
        "python.sh",
        "agents.sh",
        "sprites.sh",
        "aws.sh",
        "docker.sh"
    ),
    default_ami_selector=AmiSelectorConfig(
        owner="099720109477",
        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
        filters={"architecture": ("x86_64",)},
    ),
    subnet_cidr="10.0.3.0/24",
    instance_type="t3.small",
    volume_size=16,
    spot_price="0.1",
)
validate_environment_spec(_ENVIRONMENT_SPEC)

ENVIRONMENT_SPEC = _ENVIRONMENT_SPEC
