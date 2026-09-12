"""Verify SSH cloud-init data on Spot and on-demand workstation launches."""

import base64
import json
from dataclasses import replace
from email import policy
from email.parser import BytesParser
from unittest.mock import patch

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from .test_workstation_stack import TEST_SPEC, WorkstationStack


@pytest.mark.parametrize("purchase_mode", ["spot", "on_demand"])
@pytest.mark.parametrize("access_mode", ["ssh", "ssm", "both"])
@pytest.mark.parametrize(
    "ami_source,bootstrap_on_restored_ami",
    [
        ("default", False),
        ("selected", False),
        ("selected", True),
    ],
)
@pytest.mark.parametrize("keys", [(), ("ssh-ed25519 AAAA alice", "ssh-rsa AAAA bob")])
def test_ssh_keys_in_launch_user_data(
    purchase_mode: str,
    access_mode: str,
    ami_source: str,
    bootstrap_on_restored_ami: bool,
    keys: tuple[str, ...],
) -> None:
    """Fresh and restored launches install keys independently of bootstrap."""
    script = "#!/bin/bash\necho bootstrap\n"
    bootstrap = base64.b64encode(script.encode()).decode()
    with (
        patch("workstation.workstation_stack.resolve_ami_id", return_value="ami-test"),
        patch(
            "workstation.workstation_stack.build_bootstrap_user_data",
            return_value=bootstrap,
        ) as stack_bootstrap,
        patch(
            "workstation_core.cdk_helpers.build_bootstrap_user_data",
            return_value=bootstrap,
        ) as fleet_bootstrap,
    ):
        stack = WorkstationStack(
            cdk.App(),
            "SshKeysTest",
            shared_igw_id="igw-test",
            shared_vpc_id="vpc-test",
            shared_vpc_cidr_block="10.0.0.0/16",
            shared_ssm_clients_security_group_id="sg-clients",
            shared_ssm_instance_profile_arn=(
                "arn:aws:iam::111111111111:instance-profile/test"
            ),
            environment_spec=replace(TEST_SPEC, ssh_authorized_keys=keys),
            purchase_mode=purchase_mode,
            access_mode=access_mode,
            ami_source=ami_source,
            selected_ami_id="ami-test" if ami_source == "selected" else None,
            bootstrap_on_restored_ami=bootstrap_on_restored_ami,
            env=cdk.Environment(account="111111111111", region="us-west-2"),
        )
        template = Template.from_stack(stack)

    if ami_source == "selected" and not bootstrap_on_restored_ami:
        stack_bootstrap.assert_not_called()
        fleet_bootstrap.assert_not_called()
    resource_type = (
        "AWS::EC2::Instance" if purchase_mode == "on_demand" else "AWS::EC2::SpotFleet"
    )
    properties = next(iter(template.find_resources(resource_type).values()))[
        "Properties"
    ]
    launch = (
        properties
        if purchase_mode == "on_demand"
        else (properties["SpotFleetRequestConfigData"]["LaunchSpecifications"][0])
    )
    if access_mode == "ssm":
        assert "KeyName" not in launch
    else:
        assert launch["KeyName"] == "aws_key"
    includes_bootstrap = ami_source == "default" or bootstrap_on_restored_ami
    if not keys:
        if includes_bootstrap:
            assert launch["UserData"] == bootstrap
        else:
            assert "UserData" not in launch
        return

    payload = base64.b64decode(launch["UserData"])
    if includes_bootstrap:
        message = BytesParser(policy=policy.default).parsebytes(payload)
        config_part, script_part = list(message.iter_parts())
        assert config_part.get_content_type() == "text/cloud-config"
        assert script_part.get_content_type() == "text/x-shellscript"
        assert script_part.get_content() == script
        config = config_part.get_content()
    else:
        config = payload.decode()
    assert json.loads(config.split("\n", 1)[1]) == {"ssh_authorized_keys": list(keys)}
