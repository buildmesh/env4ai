"""Unit tests for canonical environment specification naming behavior."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from workstation_core import (
    AmiSelectorConfig,
    EnvironmentSpec,
    validate_environment_spec,
)


def _load_module(module_name: str, file_path: Path) -> object:
    """Load a module from an explicit file path.

    Args:
        module_name: Unique module name to register.
        file_path: Target Python file path.

    Returns:
        Imported module object.
    """
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to create import spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EnvironmentSpecTests(unittest.TestCase):
    """Validate environment naming derivation and validation logic."""

    @staticmethod
    def _load_environment_specs() -> tuple[EnvironmentSpec, EnvironmentSpec, EnvironmentSpec]:
        """Load representative environment spec instances from environment-local modules."""
        aws_root = Path(__file__).resolve().parents[3]
        gastown_module = _load_module(
            "gastown_environment_config",
            aws_root / "gastown" / "environment_config.py",
        )
        builder_module = _load_module(
            "builder_environment_config",
            aws_root / "builder" / "environment_config.py",
        )
        codereview_module = _load_module(
            "codereview_environment_config",
            aws_root / "codereview" / "environment_config.py",
        )
        return (
            gastown_module.ENVIRONMENT_SPEC,
            builder_module.ENVIRONMENT_SPEC,
            codereview_module.ENVIRONMENT_SPEC,
        )

    def test_environment_specs_derive_required_names(self) -> None:
        """Expected: both environments expose required derived naming outputs."""
        gastown_spec, builder_spec, _ = self._load_environment_specs()

        self.assertEqual("GastownWorkstationStack", gastown_spec.stack_name)
        self.assertEqual("GastownSpotFleet", gastown_spec.spot_fleet_logical_id)
        self.assertEqual("gastown_", gastown_spec.ami_prefix)
        self.assertEqual("gastown-workstation", gastown_spec.ssh_alias)

        self.assertEqual("BuilderWorkstationStack", builder_spec.stack_name)
        self.assertEqual("BuilderSpotFleet", builder_spec.spot_fleet_logical_id)
        self.assertEqual("builder_", builder_spec.ami_prefix)
        self.assertEqual("builder-workstation", builder_spec.ssh_alias)

    def test_environment_specs_have_unique_outputs(self) -> None:
        """Edge: derived names differ between environments to avoid collisions."""
        gastown_spec, builder_spec, _ = self._load_environment_specs()

        self.assertNotEqual(gastown_spec.stack_name, builder_spec.stack_name)
        self.assertNotEqual(
            gastown_spec.spot_fleet_logical_id,
            builder_spec.spot_fleet_logical_id,
        )
        self.assertNotEqual(gastown_spec.ami_prefix, builder_spec.ami_prefix)
        self.assertNotEqual(gastown_spec.ssh_alias, builder_spec.ssh_alias)
        self.assertEqual("GastownVPC", gastown_spec.construct_id("VPC"))
        self.assertEqual("BuilderVPC", builder_spec.construct_id("VPC"))

    def test_environment_specs_define_unique_subnet_cidrs(self) -> None:
        """Expected: each environment spec declares an explicit, distinct subnet CIDR."""
        gastown_spec, builder_spec, codereview_spec = self._load_environment_specs()

        self.assertEqual("10.0.1.0/24", gastown_spec.subnet_cidr)
        self.assertEqual("10.0.2.0/24", builder_spec.subnet_cidr)
        self.assertEqual("10.0.3.0/24", codereview_spec.subnet_cidr)
        self.assertEqual(
            3,
            len({gastown_spec.subnet_cidr, builder_spec.subnet_cidr, codereview_spec.subnet_cidr}),
        )

    def test_validate_environment_spec_rejects_invalid_values(self) -> None:
        """Failure: invalid or empty required fields are rejected."""
        with self.assertRaisesRegex(
            ValueError,
            "EnvironmentSpec.volume_size must be greater than 0",
        ):
            validate_environment_spec(
                EnvironmentSpec(
                    environment_key="broken",
                    display_name="Broken",
                    bootstrap_files=("deps.sh",),
                    default_ami_selector=AmiSelectorConfig(
                        owner="099720109477",
                        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
                        filters={"architecture": ("x86_64",)},
                    ),
                    subnet_cidr="10.0.9.0/24",
                    instance_type="t3.large",
                    volume_size=0,
                    spot_price="0.1",
                )
            )

    def test_validate_environment_spec_rejects_invalid_subnet_cidr(self) -> None:
        """Failure: malformed subnet CIDRs are rejected with actionable guidance."""
        with self.assertRaisesRegex(
            ValueError,
            "EnvironmentSpec.subnet_cidr must be a valid IPv4 CIDR block.",
        ):
            validate_environment_spec(
                EnvironmentSpec(
                    environment_key="broken",
                    display_name="Broken",
                    bootstrap_files=("deps.sh",),
                    default_ami_selector=AmiSelectorConfig(
                        owner="099720109477",
                        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
                        filters={"architecture": ("x86_64",)},
                    ),
                    subnet_cidr="not-a-cidr",
                    instance_type="t3.large",
                    volume_size=16,
                    spot_price="0.1",
                )
            )

    def test_validate_environment_spec_rejects_subnet_outside_shared_vpc(self) -> None:
        """Failure: subnets outside the shared VPC CIDR are rejected."""
        with self.assertRaisesRegex(
            ValueError,
            "EnvironmentSpec.subnet_cidr must fit within the shared VPC CIDR 10.0.0.0/16.",
        ):
            validate_environment_spec(
                EnvironmentSpec(
                    environment_key="broken",
                    display_name="Broken",
                    bootstrap_files=("deps.sh",),
                    default_ami_selector=AmiSelectorConfig(
                        owner="099720109477",
                        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
                        filters={"architecture": ("x86_64",)},
                    ),
                    subnet_cidr="192.168.1.0/24",
                    instance_type="t3.large",
                    volume_size=16,
                    spot_price="0.1",
                )
            )


if __name__ == "__main__":
    unittest.main()
