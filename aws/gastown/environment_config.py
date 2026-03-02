"""Canonical environment specification for the gastown workstation."""

from workstation_core import AmiSelectorConfig, EnvironmentSpec, validate_environment_spec

GASTOWN_ENVIRONMENT_SPEC = EnvironmentSpec(
    environment_key="gastown",
    display_name="Gastown",
    bootstrap_files=(
        "deps.sh",
        "python.sh",
        "docker.sh",
        "android.sh",
        "agents.sh",
        "gastown.sh",
    ),
    default_ami_selector=AmiSelectorConfig(
        owner="099720109477",
        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
        filters={"architecture": ("x86_64",)},
    ),
    instance_type="t3.xlarge",
    volume_size=16,
    spot_price="0.1",
)
validate_environment_spec(GASTOWN_ENVIRONMENT_SPEC)

ENVIRONMENT_SPEC = GASTOWN_ENVIRONMENT_SPEC
