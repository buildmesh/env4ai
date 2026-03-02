#!/usr/bin/env python3
import aws_cdk as cdk

from environment_config import BUILDER_ENVIRONMENT_SPEC
from builder_workstation.builder_workstation_stack import BuilderWorkstationStack
from workstation_core.runtime_resolution import get_account, get_region


def main() -> None:
    """Synthesize the CDK app for this environment."""
    app = cdk.App()
    BuilderWorkstationStack(
        app,
        BUILDER_ENVIRONMENT_SPEC.stack_name,
        environment_spec=BUILDER_ENVIRONMENT_SPEC,
        env=cdk.Environment(account=get_account(), region=get_region()),
    )
    app.synth()


if __name__ == "__main__":
    main()
