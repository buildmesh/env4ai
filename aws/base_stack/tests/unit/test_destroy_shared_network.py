"""Unit tests for the shared-network destroy wrapper script."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from destroy_shared_network import main, parse_args  # noqa: E402


class DestroySharedNetworkScriptTests(unittest.TestCase):
    """Validate the shared-network operator wrapper behavior."""

    def test_parse_args_accepts_optional_region_and_profile(self) -> None:
        """Expected: wrapper accepts optional AWS profile and region overrides."""
        args = parse_args(["--profile", "dev", "--region", "us-west-2"])

        self.assertEqual("dev", args.profile)
        self.assertEqual("us-west-2", args.region)

    def test_main_delegates_to_shared_network_destroy_orchestration(self) -> None:
        """Edge: wrapper forwards parsed arguments to shared orchestration."""
        with patch(
            "destroy_shared_network.destroy_shared_network_stack",
            return_value=0,
        ) as destroy_shared_network_stack:
            result = main(["--profile", "dev"])

        self.assertEqual(0, result)
        destroy_shared_network_stack.assert_called_once_with(profile="dev", region=None)

    def test_main_propagates_destroy_failures(self) -> None:
        """Failure: shared-network teardown errors are not swallowed."""
        with patch(
            "destroy_shared_network.destroy_shared_network_stack",
            side_effect=RuntimeError("shared network still in use"),
        ):
            with self.assertRaisesRegex(RuntimeError, "shared network still in use"):
                main([])


if __name__ == "__main__":
    unittest.main()
