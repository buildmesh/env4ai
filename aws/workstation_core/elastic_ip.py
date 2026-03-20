"""Elastic IP find, create, associate, and release helpers."""

from __future__ import annotations

from typing import Any


def find_eip_by_name(ec2_client: Any, name: str) -> dict[str, str] | None:
    """Find an Elastic IP allocation by its Name tag.

    Args:
        ec2_client: Boto3 EC2 client.
        name: Name tag value to search for.

    Returns:
        Dict with ``allocation_id`` and ``public_ip`` when found, otherwise ``None``.
    """
    response = ec2_client.describe_addresses(
        Filters=[{"Name": "tag:Name", "Values": [name]}]
    )
    addresses = response.get("Addresses", [])
    if not addresses:
        return None
    address = addresses[0]
    return {
        "allocation_id": address["AllocationId"],
        "public_ip": address["PublicIp"],
    }


def create_eip(ec2_client: Any, name: str) -> dict[str, str]:
    """Allocate a new VPC Elastic IP and tag it with a Name.

    Args:
        ec2_client: Boto3 EC2 client.
        name: Name tag value to apply.

    Returns:
        Dict with ``allocation_id`` and ``public_ip``.

    Raises:
        ValueError: If name is empty.
    """
    if not name or not name.strip():
        raise ValueError("name must be non-empty.")
    response = ec2_client.allocate_address(Domain="vpc")
    allocation_id = response["AllocationId"]
    public_ip = response["PublicIp"]
    ec2_client.create_tags(
        Resources=[allocation_id],
        Tags=[{"Key": "Name", "Value": name}],
    )
    return {"allocation_id": allocation_id, "public_ip": public_ip}


def find_or_create_eip(ec2_client: Any, name: str) -> dict[str, str]:
    """Find an existing Elastic IP by Name tag or create a new one.

    Args:
        ec2_client: Boto3 EC2 client.
        name: Name tag value to match or apply.

    Returns:
        Dict with ``allocation_id`` and ``public_ip``.
    """
    existing = find_eip_by_name(ec2_client, name)
    if existing is not None:
        return existing
    return create_eip(ec2_client, name)


def associate_eip_with_instance(
    ec2_client: Any,
    allocation_id: str,
    instance_id: str,
) -> None:
    """Associate an Elastic IP with an EC2 instance.

    Replaces any auto-assigned public IP on the instance with the EIP.
    ``AllowReassociation=True`` permits re-associating an already-associated EIP.

    Args:
        ec2_client: Boto3 EC2 client.
        allocation_id: EIP allocation ID.
        instance_id: Target EC2 instance ID.
    """
    ec2_client.associate_address(
        AllocationId=allocation_id,
        InstanceId=instance_id,
        AllowReassociation=True,
    )


def release_eip(ec2_client: Any, allocation_id: str) -> None:
    """Release an Elastic IP back to the AWS pool.

    Args:
        ec2_client: Boto3 EC2 client.
        allocation_id: EIP allocation ID to release.
    """
    ec2_client.release_address(AllocationId=allocation_id)
