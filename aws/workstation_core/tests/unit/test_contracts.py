"""Unit tests for workstation_core shared contracts."""

import unittest

from workstation_core import (
    CoreConfig,
    OrchestrationPlan,
    RuntimeContext,
    build_stack_name,
    validate_plan,
)
from workstation_core.config import validate_config
from workstation_core.runtime import describe_runtime


class WorkstationCoreContractTests(unittest.TestCase):
    """Validate expected import and contract behavior for workstation_core."""

    def test_import_and_contract_types_are_available(self) -> None:
        """Expected: core package exposes primary contract types."""
        config = CoreConfig(
            environment="gastown",
            region="us-west-2",
            stack_prefix="workstation",
        )
        plan = OrchestrationPlan(
            environment="gastown",
            stack_name="workstation-gastown",
            action="deploy",
        )
        runtime = RuntimeContext(account_id="111111111111", profile_name="default")

        self.assertEqual(config.environment, "gastown")
        self.assertEqual(plan.action, "deploy")
        self.assertFalse(runtime.dry_run)

    def test_helpers_trim_inputs_for_stack_and_runtime_summary(self) -> None:
        """Edge: helper functions handle trimmed input values consistently."""
        stack_name = build_stack_name(stack_prefix=" workstation ", environment=" gastown ")
        runtime_summary = describe_runtime(
            RuntimeContext(account_id="111111111111", profile_name=" default ", dry_run=True)
        )

        self.assertEqual(stack_name, "workstation-gastown")
        self.assertIn("mode=dry-run", runtime_summary)

    def test_validation_rejects_empty_required_fields(self) -> None:
        """Failure: validation raises when required contract fields are empty."""
        with self.assertRaisesRegex(ValueError, "CoreConfig.environment must be non-empty"):
            validate_config(
                CoreConfig(environment="   ", region="us-west-2", stack_prefix="workstation")
            )

        with self.assertRaisesRegex(ValueError, "OrchestrationPlan.action must be non-empty"):
            validate_plan(
                OrchestrationPlan(
                    environment="gastown",
                    stack_name="workstation-gastown",
                    action=" ",
                )
            )


if __name__ == "__main__":
    unittest.main()
