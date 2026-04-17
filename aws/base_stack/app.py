#!/usr/bin/env python3
import os
from pathlib import Path
import sys
import aws_cdk as cdk
from dataclasses import dataclass

# Reason: when invoked as `python3 ../base_stack/app.py` from an env dir, CWD
# is the env dir (so environment_config.py is found) but this file lives in
# base_stack/ (so workstation/ is found via APP_DIR).
_APP_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _APP_DIR)  # finds workstation/ in base_stack/
sys.path.insert(0, os.getcwd())  # finds environment_config.py in the env dir (higher priority)

from environment_config import ENVIRONMENT_SPEC
from workstation.env4ai_network_stack import Env4aiNetworkStack
from workstation.workstation_stack import WorkstationStack
from workstation_core.config import get_shared_network_config, get_shared_network_export_name
from workstation_core.runtime_resolution import (
    get_account,
    get_region,
    parse_optional_bool_context,
    parse_optional_text_context,
)

_VALID_ACCESS_MODES = frozenset({"ssh", "ssm", "both"})


@dataclass(frozen=True, slots=True)
class SharedNetworkImports:
    """Imported shared-network resources used by the workstation stack."""

    vpc_id: str
    vpc_cidr_block: str
    internet_gateway_id: str
    ssm_clients_security_group_id: str
    ssm_instance_profile_arn: str


def load_shared_network_imports() -> SharedNetworkImports:
    """Load shared-network CloudFormation imports as stack-local tokens."""
    return SharedNetworkImports(
        vpc_id=cdk.Fn.import_value(get_shared_network_export_name("VpcId")),
        vpc_cidr_block=cdk.Fn.import_value(get_shared_network_export_name("VpcCidr")),
        internet_gateway_id=cdk.Fn.import_value(
            get_shared_network_export_name("InternetGatewayId")
        ),
        ssm_clients_security_group_id=cdk.Fn.import_value(
            get_shared_network_export_name("SsmClientsSecurityGroupId")
        ),
        ssm_instance_profile_arn=cdk.Fn.import_value(
            get_shared_network_export_name("SsmInstanceProfileArn")
        ),
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
    verbose_bootstrap_context = app.node.try_get_context("verbose_bootstrap_resolution")
    verbose_bootstrap_resolution = False
    if verbose_bootstrap_context is not None:
        verbose_bootstrap_resolution = parse_optional_bool_context(
            value=verbose_bootstrap_context,
            context_key="verbose_bootstrap_resolution",
        )
    access_mode = str(getattr(ENVIRONMENT_SPEC, "default_access_mode", "ssh")).strip() or "ssh"
    access_mode_context = parse_optional_text_context(app.node.try_get_context("access_mode"))
    if access_mode_context is not None:
        if access_mode_context not in _VALID_ACCESS_MODES:
            raise RuntimeError("access_mode context must be one of: ssh, ssm, both")
        access_mode = access_mode_context
    public_ip_enabled = access_mode in {"ssh", "both"}
    public_ip_enabled_context = app.node.try_get_context("public_ip_enabled")
    if public_ip_enabled_context is not None:
        public_ip_enabled = parse_optional_bool_context(
            value=public_ip_enabled_context,
            context_key="public_ip_enabled",
        )
    if access_mode in {"ssh", "both"}:
        public_ip_enabled = True
    eip_allocation_id = parse_optional_text_context(app.node.try_get_context("eip_allocation_id"))
    env = cdk.Environment(account=get_account(), region=get_region())
    shared_network_config = get_shared_network_config()
    Env4aiNetworkStack(app, shared_network_config.stack_name, env=env)
    shared_network = load_shared_network_imports()

    workstation_stack = WorkstationStack(
        app,
        ENVIRONMENT_SPEC.stack_name,
        shared_igw_id=shared_network.internet_gateway_id,
        shared_vpc_id=shared_network.vpc_id,
        shared_vpc_cidr_block=shared_network.vpc_cidr_block,
        ami_id_override=ami_id_override,
        bootstrap_on_restored_ami=bootstrap_on_restored_ami,
        verbose_bootstrap_resolution=verbose_bootstrap_resolution,
        eip_allocation_id=eip_allocation_id,
        access_mode=access_mode,
        public_ip_enabled=public_ip_enabled,
        shared_ssm_clients_security_group_id=shared_network.ssm_clients_security_group_id,
        shared_ssm_instance_profile_arn=shared_network.ssm_instance_profile_arn,
        environment_spec=ENVIRONMENT_SPEC,
        env=env,
    )
    app.synth()


if __name__ == "__main__":
    main()
