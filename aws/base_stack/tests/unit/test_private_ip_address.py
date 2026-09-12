"""Synthesis coverage for optional primary private IPv4 assignment."""

from dataclasses import replace

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from .test_workstation_stack import TEST_SPEC, WorkstationStack


@pytest.mark.parametrize("purchase_mode", ["spot", "on_demand"])
@pytest.mark.parametrize("access_mode", ["ssh", "ssm", "both"])
@pytest.mark.parametrize("address", [None, "10.0.99.10"])
def test_private_ip_launch_template(
    purchase_mode: str, access_mode: str, address: str | None
) -> None:
    """Both purchase modes preserve networking with explicit or automatic IPs."""
    stack = WorkstationStack(
        cdk.App(),
        "PrivateIpTest",
        shared_igw_id="igw-test",
        shared_vpc_id="vpc-test",
        shared_vpc_cidr_block="10.0.0.0/16",
        shared_ssm_clients_security_group_id="sg-clients",
        shared_ssm_instance_profile_arn=(
            "arn:aws:iam::111111111111:instance-profile/test"
        ),
        environment_spec=replace(TEST_SPEC, private_ip_address=address),
        purchase_mode=purchase_mode,
        access_mode=access_mode,
        ami_source="selected",
        selected_ami_id="ami-test",
        env=cdk.Environment(account="111111111111", region="us-west-2"),
    )
    template = Template.from_stack(stack)
    subnet = next(iter(template.find_resources("AWS::EC2::Subnet").values()))
    assert subnet["Properties"]["MapPublicIpOnLaunch"] == (access_mode != "ssm")
    resource_type = (
        "AWS::EC2::Instance" if purchase_mode == "on_demand" else "AWS::EC2::SpotFleet"
    )
    properties = next(iter(template.find_resources(resource_type).values()))[
        "Properties"
    ]
    if purchase_mode == "on_demand":
        assert properties.get("PrivateIpAddress") == address
        assert ("PrivateIpAddress" in properties) == (address is not None)
        assert "SubnetId" in properties
        assert properties["SecurityGroupIds"]
    else:
        launch = properties["SpotFleetRequestConfigData"]["LaunchSpecifications"][0]
        if address is None:
            assert "NetworkInterfaces" not in launch
            assert "SubnetId" in launch
            assert launch["SecurityGroups"]
        else:
            assert "SubnetId" not in launch
            assert "SecurityGroups" not in launch
            (interface,) = launch["NetworkInterfaces"]
            assert interface["DeviceIndex"] == 0
            assert interface["DeleteOnTermination"] is True
            assert "SubnetId" in interface
            assert interface["Groups"]
            assert interface["PrivateIpAddresses"] == [
                {"PrivateIpAddress": address, "Primary": True}
            ]
