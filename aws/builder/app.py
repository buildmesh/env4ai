#!/usr/bin/env python3
import aws_cdk as cdk

from environment_config import ENVIRONMENT_SPEC
from workstation.workstation_stack import WorkstationStack
from workstation_core.runtime_resolution import (
    get_account,
    get_region,
    parse_optional_bool_context,
    parse_optional_text_context,
)


def main() -> None:
    """Synthesize the CDK app for this environment."""
    app = cdk.App()
    ami_id_override = parse_optional_text_context(app.node.try_get_context("ami_id"))
    bootstrap_on_restored_context = app.node.try_get_context("bootstrap_on_restored_ami")
    bootstrap_on_restored_ami = False
    if bootstrap_on_restored_context is not None:
        bootstrap_on_restored_ami = parse_optional_bool_context(
            value=bootstrap_on_restored_context,
            context_key="bootstrap_on_restored_ami",
        )
    eip_allocation_id = parse_optional_text_context(app.node.try_get_context("eip_allocation_id"))

    WorkstationStack(
        app,
        ENVIRONMENT_SPEC.stack_name,
        ami_id_override=ami_id_override,
        bootstrap_on_restored_ami=bootstrap_on_restored_ami,
        eip_allocation_id=eip_allocation_id,
        environment_spec=ENVIRONMENT_SPEC,
        env=cdk.Environment(account=get_account(), region=get_region()),
    )
    app.synth()


if __name__ == "__main__":
    main()
