from aws_cdk import (
    CfnOutput,
    Fn,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
)
from constructs import Construct
import base64


def resolve_subnet_availability_zone(availability_zone_index: int = 0) -> str:
    """Return a dynamic AZ token from the deployment region.

    Args:
        availability_zone_index: The zero-based index into region AZs.

    Returns:
        A CloudFormation token selecting an AZ from ``Fn::GetAZs``.

    Raises:
        ValueError: If ``availability_zone_index`` is negative.
    """
    if availability_zone_index < 0:
        raise ValueError("availability_zone_index must be greater than or equal to 0")

    return Fn.select(availability_zone_index, Fn.get_azs())


def build_bootstrap_user_data() -> str:
    """Return base64-encoded bootstrap user data for fresh Ubuntu launches.

    Returns:
        Base64-encoded concatenation of init scripts.
    """
    filenames = [
        "deps.sh",
        "python.sh",
        "docker.sh",
        "android.sh",
        "agents.sh",
        "gastown.sh",
    ]

    user_data_script = ""
    for filename in filenames:
        with open(f"init/{filename}", "r", encoding="utf-8") as fd:
            user_data_script += fd.read()

    return base64.b64encode(user_data_script.encode("utf-8")).decode("utf-8")


class GastownWorkstationStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        availability_zone_index: int = 0,
        ami_id_override: str | None = None,
        bootstrap_on_restored_ami: bool = False,
        **kwargs,
    ) -> None:
        """Create the workstation infrastructure stack.

        Args:
            scope: Construct scope.
            construct_id: Logical construct id.
            availability_zone_index: Selected AZ index for workstation subnet.
            ami_id_override: Optional explicit AMI ID used for deploy-time restore flows.
            bootstrap_on_restored_ami: When ``True``, include bootstrap user data even
                when launching from ``ami_id_override``.
            **kwargs: Additional ``Stack`` keyword args.
        """
        super().__init__(scope, construct_id, **kwargs)

        # Create a new VPC named 'GastownVPC'
        vpc = ec2.Vpc(self, "GastownVPC",
            max_azs=1,
            subnet_configuration=[]
        )

        igw = ec2.CfnInternetGateway(self, "GastownIGW")
        ec2.CfnVPCGatewayAttachment(self, "GastownIGWAttachment", vpc_id=vpc.vpc_id, internet_gateway_id=igw.ref)

        local_zone_subnet = ec2.CfnSubnet(self, "Lax1Subnet",
            availability_zone=resolve_subnet_availability_zone(availability_zone_index),
            cidr_block="10.0.100.0/24",
            vpc_id=vpc.vpc_id,
            map_public_ip_on_launch=True
        )


        route_table = ec2.CfnRouteTable(self, "GastownRouteTable", vpc_id=vpc.vpc_id)
        ec2.CfnRoute(self, "GastownDefaultRoute", route_table_id=route_table.ref, destination_cidr_block="0.0.0.0/0", gateway_id=igw.ref)
        ec2.CfnSubnetRouteTableAssociation(self, "GastownSubnetRouteTableAssociation", subnet_id=local_zone_subnet.ref, route_table_id=route_table.ref)

        # Security group for SSH (VNC tunneled over SSH)
        sg = ec2.SecurityGroup(self, "GastownSG", vpc=vpc)
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "Allow SSH")

        ami_id = ami_id_override.strip() if ami_id_override else ""
        if not ami_id:
            # Default path: use Canonical Ubuntu image unless a deploy override is provided.
            ubuntu_ami = ec2.MachineImage.lookup(
                name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
                owners=["099720109477"],  # Canonical
                filters={"architecture": ["x86_64"]}
            )
            ami_id = ubuntu_ami.get_image(self).image_id

        # Reason: restored AMIs already contain bootstrapped state by design.
        use_bootstrap = not ami_id_override or bootstrap_on_restored_ami
        launch_specification: dict[str, object] = {
            "image_id": ami_id,
            "instance_type": "t3.xlarge",
            "key_name": "aws_key",
            "security_groups": [{"groupId": sg.security_group_id}],
            "subnet_id": local_zone_subnet.ref,
            "block_device_mappings": [
                {
                    "deviceName": "/dev/sda1",  # Typical root device for Ubuntu AMIs
                    "ebs": {
                        "deleteOnTermination": True,
                        "volumeSize": 16,        # Request 24 GB
                        "volumeType": "gp3",     # Use gp3 for best price/performance
                        "encrypted": False       # Set to True if encryption is required
                    }
                }
            ],
        }
        if use_bootstrap:
            launch_specification["user_data"] = build_bootstrap_user_data()

        # Spot Fleet Request
        ec2.CfnSpotFleet(self, "GastownSpotFleet",
            spot_fleet_request_config_data=ec2.CfnSpotFleet.SpotFleetRequestConfigDataProperty(
                iam_fleet_role="arn:aws:iam::{}:role/aws-ec2-spot-fleet-tagging-role".format(self.account),
                target_capacity=1,
                spot_price="0.1",
                launch_specifications=[
                    ec2.CfnSpotFleet.SpotFleetLaunchSpecificationProperty(**launch_specification)
                ]
            )
        )
