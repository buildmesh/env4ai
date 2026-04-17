"""Regression tests for the scoped deployer IAM policy."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


_POLICY_PATH = Path(__file__).resolve().parents[2] / "deployer-policy.json"
_SSM_ROLE_ARN = "arn:aws:iam::*:role/Env4aiNetworkStack-SsmEc2InstanceRole*"
_SSM_PROFILE_ARN = (
    "arn:aws:iam::*:instance-profile/Env4aiNetworkStack-SsmEc2InstanceProfile*"
)


def _load_policy() -> dict[str, object]:
    """Load the deployer policy JSON from disk."""
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


class DeployerPolicyTests(unittest.TestCase):
    """Validate least-privilege scoping for deployer-policy.json."""

    def test_ssm_iam_statement_is_scoped_to_shared_role_and_profile(self) -> None:
        """Expected: shared SSM IAM lifecycle actions avoid wildcard resources."""
        policy = _load_policy()
        statement = next(
            item
            for item in policy["Statement"]
            if item["Sid"] == "IamRoleAndInstanceProfileForSsm"
        )

        self.assertEqual(
            statement["Resource"],
            [_SSM_ROLE_ARN, _SSM_PROFILE_ARN],
        )
        self.assertNotEqual(statement["Resource"], "*")

    def test_ssm_role_policy_attachment_only_allows_managed_instance_core(self) -> None:
        """Edge: only AmazonSSMManagedInstanceCore can be attached to the shared role."""
        policy = _load_policy()
        statement = next(
            item
            for item in policy["Statement"]
            if item["Sid"] == "SsmRoleManagedPolicyAttachment"
        )

        self.assertEqual(statement["Resource"], _SSM_ROLE_ARN)
        self.assertEqual(
            statement["Condition"],
            {
                "ArnEquals": {
                    "iam:PolicyARN": "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
                }
            },
        )

    def test_pass_role_is_limited_to_shared_ssm_ec2_role(self) -> None:
        """Failure case: pass-role must not remain wildcard for EC2 launches."""
        policy = _load_policy()
        statement = next(
            item for item in policy["Statement"] if item["Sid"] == "PassSsmEc2RoleToEc2"
        )

        self.assertEqual(statement["Resource"], _SSM_ROLE_ARN)
        self.assertNotEqual(statement["Resource"], "*")


if __name__ == "__main__":
    unittest.main()
