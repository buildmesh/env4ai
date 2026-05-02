"""Canonical environment specification for the builder workstation."""

from workstation_core import AmiSelectorConfig, EnvironmentSpec, validate_environment_spec

_ENVIRONMENT_SPEC = EnvironmentSpec(
    environment_key="teslamate",
    display_name="TeslaMate",
    bootstrap_files=(
        "deps.sh",
        "docker.sh",
        "teslamate.sh"
    ),
    default_ami_selector=AmiSelectorConfig(
        owner="099720109477",
        name="ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*",
        filters={"architecture": ("x86_64",)},
    ),
    subnet_cidr="10.0.8.0/24",
    instance_type="t3.small",
    volume_size=20,
    spot_price="0.1",
    default_access_mode="both",
)
validate_environment_spec(_ENVIRONMENT_SPEC)

ENVIRONMENT_SPEC = _ENVIRONMENT_SPEC
