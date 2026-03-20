"""Unit tests for Elastic IP lifecycle helpers."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, call

from workstation_core.elastic_ip import (
    associate_eip_with_instance,
    create_eip,
    find_eip_by_name,
    find_or_create_eip,
    release_eip,
)


class FindEipByNameTests(unittest.TestCase):
    def test_returns_allocation_and_ip_when_eip_exists(self) -> None:
        """Expected: matching EIP by Name tag returns allocation_id and public_ip."""
        ec2_client = Mock()
        ec2_client.describe_addresses.return_value = {
            "Addresses": [
                {"AllocationId": "eipalloc-abc123", "PublicIp": "1.2.3.4"}
            ]
        }

        result = find_eip_by_name(ec2_client, "gastown")

        self.assertEqual({"allocation_id": "eipalloc-abc123", "public_ip": "1.2.3.4"}, result)
        ec2_client.describe_addresses.assert_called_once_with(
            Filters=[{"Name": "tag:Name", "Values": ["gastown"]}]
        )

    def test_returns_none_when_no_eip_matches(self) -> None:
        """Edge: no matching EIP returns None."""
        ec2_client = Mock()
        ec2_client.describe_addresses.return_value = {"Addresses": []}

        result = find_eip_by_name(ec2_client, "gastown")

        self.assertIsNone(result)

    def test_returns_first_match_when_multiple_eips_share_name(self) -> None:
        """Edge: first address is returned when multiple share the same Name tag."""
        ec2_client = Mock()
        ec2_client.describe_addresses.return_value = {
            "Addresses": [
                {"AllocationId": "eipalloc-first", "PublicIp": "1.1.1.1"},
                {"AllocationId": "eipalloc-second", "PublicIp": "2.2.2.2"},
            ]
        }

        result = find_eip_by_name(ec2_client, "gastown")

        self.assertEqual("eipalloc-first", result["allocation_id"])


class CreateEipTests(unittest.TestCase):
    def test_allocates_vpc_eip_and_applies_name_tag(self) -> None:
        """Expected: allocates a VPC-domain EIP and tags it with the given Name."""
        ec2_client = Mock()
        ec2_client.allocate_address.return_value = {
            "AllocationId": "eipalloc-new001",
            "PublicIp": "5.6.7.8",
        }

        result = create_eip(ec2_client, "gastown")

        self.assertEqual({"allocation_id": "eipalloc-new001", "public_ip": "5.6.7.8"}, result)
        ec2_client.allocate_address.assert_called_once_with(Domain="vpc")
        ec2_client.create_tags.assert_called_once_with(
            Resources=["eipalloc-new001"],
            Tags=[{"Key": "Name", "Value": "gastown"}],
        )

    def test_raises_on_empty_name(self) -> None:
        """Failure: empty name is rejected before any AWS calls."""
        ec2_client = Mock()

        with self.assertRaisesRegex(ValueError, "name must be non-empty"):
            create_eip(ec2_client, "  ")

        ec2_client.allocate_address.assert_not_called()


class FindOrCreateEipTests(unittest.TestCase):
    def test_returns_existing_eip_without_creating(self) -> None:
        """Expected: when matching EIP exists, it is returned without allocating a new one."""
        ec2_client = Mock()
        ec2_client.describe_addresses.return_value = {
            "Addresses": [{"AllocationId": "eipalloc-existing", "PublicIp": "9.9.9.9"}]
        }

        result = find_or_create_eip(ec2_client, "gastown")

        self.assertEqual({"allocation_id": "eipalloc-existing", "public_ip": "9.9.9.9"}, result)
        ec2_client.allocate_address.assert_not_called()

    def test_creates_new_eip_when_none_exists(self) -> None:
        """Edge: when no matching EIP exists, a new one is allocated and tagged."""
        ec2_client = Mock()
        ec2_client.describe_addresses.return_value = {"Addresses": []}
        ec2_client.allocate_address.return_value = {
            "AllocationId": "eipalloc-brand-new",
            "PublicIp": "10.0.0.1",
        }

        result = find_or_create_eip(ec2_client, "gastown")

        self.assertEqual({"allocation_id": "eipalloc-brand-new", "public_ip": "10.0.0.1"}, result)
        ec2_client.allocate_address.assert_called_once_with(Domain="vpc")


class AssociateEipTests(unittest.TestCase):
    def test_associates_eip_with_instance(self) -> None:
        """Expected: associates the EIP with the given instance with reassociation allowed."""
        ec2_client = Mock()

        associate_eip_with_instance(ec2_client, "eipalloc-abc123", "i-0abc123")

        ec2_client.associate_address.assert_called_once_with(
            AllocationId="eipalloc-abc123",
            InstanceId="i-0abc123",
            AllowReassociation=True,
        )

    def test_propagates_client_error_on_association_failure(self) -> None:
        """Failure: client errors from associate_address propagate to the caller."""
        ec2_client = Mock()
        ec2_client.associate_address.side_effect = RuntimeError("insufficient capacity")

        with self.assertRaisesRegex(RuntimeError, "insufficient capacity"):
            associate_eip_with_instance(ec2_client, "eipalloc-abc123", "i-0abc123")


class ReleaseEipTests(unittest.TestCase):
    def test_releases_eip_by_allocation_id(self) -> None:
        """Expected: releases the EIP using its allocation ID."""
        ec2_client = Mock()

        release_eip(ec2_client, "eipalloc-abc123")

        ec2_client.release_address.assert_called_once_with(AllocationId="eipalloc-abc123")

    def test_propagates_client_error_on_release_failure(self) -> None:
        """Failure: client errors from release_address propagate to the caller."""
        ec2_client = Mock()
        ec2_client.release_address.side_effect = RuntimeError("address not found")

        with self.assertRaisesRegex(RuntimeError, "address not found"):
            release_eip(ec2_client, "eipalloc-abc123")


if __name__ == "__main__":
    unittest.main()
