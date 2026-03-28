"""Test fixture: minimal EnvironmentSpec for base_stack unit tests.

This module satisfies the ``from environment_config import ENVIRONMENT_SPEC``
import that WorkstationStack and app.py perform at module load time.  Tests
that need a concrete spec should either import ENVIRONMENT_SPEC from here or
construct their own EnvironmentSpec inline.
"""

from workstation_core import AmiSelectorConfig, EnvironmentSpec

ENVIRONMENT_SPEC = EnvironmentSpec(
    environment_key="test",
    display_name="Test",
    bootstrap_files=("bootstrap.sh",),
    default_ami_selector=AmiSelectorConfig(
        owner="099720109477",
        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
        filters={"architecture": ("x86_64",)},
    ),
    subnet_cidr="10.0.99.0/24",
    instance_type="t3.micro",
    volume_size=8,
    spot_price="0.05",
)
