"""Unit tests for workstation pricing helpers."""

from __future__ import annotations

import json
import unittest
from unittest.mock import Mock

from workstation_core.pricing import (
    PriceQuote,
    format_price_per_hour,
    get_current_spot_price,
    get_on_demand_hourly_price,
    lookup_deploy_price_quote,
)


class FormatPricePerHourTests(unittest.TestCase):
    """Validate human-friendly price formatting."""

    def test_none_renders_em_dash(self) -> None:
        """Edge: missing price renders as a placeholder."""
        self.assertEqual("—", format_price_per_hour(None))

    def test_empty_string_renders_em_dash(self) -> None:
        """Edge: blank price renders as a placeholder."""
        self.assertEqual("—", format_price_per_hour("   "))

    def test_numeric_string_is_formatted_to_four_decimals(self) -> None:
        """Expected: numeric prices are normalized to four decimal places per hour."""
        self.assertEqual("$0.0832/hr", format_price_per_hour("0.0832000000"))

    def test_unparseable_price_returns_raw_value(self) -> None:
        """Edge: non-numeric strings are surfaced verbatim for diagnosis."""
        self.assertEqual("not-a-number", format_price_per_hour("not-a-number"))


class GetCurrentSpotPriceTests(unittest.TestCase):
    """Validate spot price history lookup behavior."""

    def test_returns_first_spot_price_when_history_present(self) -> None:
        """Expected: first SpotPriceHistory entry is returned as the current price."""
        ec2_client = Mock()
        ec2_client.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "0.0234"}]
        }

        result = get_current_spot_price(
            ec2_client,
            instance_type="t3.large",
            availability_zone="us-west-2a",
        )

        self.assertEqual("0.0234", result)
        kwargs = ec2_client.describe_spot_price_history.call_args.kwargs
        self.assertEqual(["t3.large"], kwargs["InstanceTypes"])
        self.assertEqual("us-west-2a", kwargs["AvailabilityZone"])

    def test_returns_none_when_history_missing(self) -> None:
        """Edge: an empty history surfaces None so callers can render a placeholder."""
        ec2_client = Mock()
        ec2_client.describe_spot_price_history.return_value = {"SpotPriceHistory": []}

        self.assertIsNone(
            get_current_spot_price(ec2_client, instance_type="t3.large")
        )

    def test_returns_none_when_describe_raises(self) -> None:
        """Failure: AWS errors degrade to None rather than aborting the caller."""
        ec2_client = Mock()
        ec2_client.describe_spot_price_history.side_effect = RuntimeError("boom")

        self.assertIsNone(
            get_current_spot_price(ec2_client, instance_type="t3.large")
        )


class GetOnDemandHourlyPriceTests(unittest.TestCase):
    """Validate Pricing API on-demand price lookup."""

    @staticmethod
    def _price_list_entry(price: str) -> str:
        """Return a minimal pricing payload mirroring AWS Pricing API output."""
        return json.dumps(
            {
                "terms": {
                    "OnDemand": {
                        "OFFER1": {
                            "priceDimensions": {
                                "DIM1": {"pricePerUnit": {"USD": price}}
                            }
                        }
                    }
                }
            }
        )

    def test_returns_price_from_pricing_api_payload(self) -> None:
        """Expected: pricing API payload is parsed to the OnDemand USD price."""
        pricing_client = Mock()
        pricing_client.get_products.return_value = {
            "PriceList": [self._price_list_entry("0.0832000000")]
        }

        result = get_on_demand_hourly_price(
            pricing_client,
            instance_type="t3.large",
            region="us-west-2",
        )

        self.assertEqual("0.0832000000", result)

    def test_returns_none_when_price_list_missing(self) -> None:
        """Edge: empty PriceList degrades to None."""
        pricing_client = Mock()
        pricing_client.get_products.return_value = {"PriceList": []}

        self.assertIsNone(
            get_on_demand_hourly_price(
                pricing_client, instance_type="t3.large", region="us-west-2"
            )
        )

    def test_returns_none_when_pricing_api_raises(self) -> None:
        """Failure: pricing API failures fall back to None."""
        pricing_client = Mock()
        pricing_client.get_products.side_effect = RuntimeError("boom")

        self.assertIsNone(
            get_on_demand_hourly_price(
                pricing_client, instance_type="t3.large", region="us-west-2"
            )
        )


class LookupDeployPriceQuoteTests(unittest.TestCase):
    """Validate combined spot/on-demand quote orchestration."""

    def test_spot_quote_includes_current_price_and_limit(self) -> None:
        """Expected: spot quote pulls current spot price and surfaces the limit."""
        ec2_client = Mock()
        ec2_client.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "0.0123"}]
        }

        quote = lookup_deploy_price_quote(
            purchase_mode="spot",
            instance_type="t3.large",
            spot_price_limit="0.10",
            region="us-west-2",
            ec2_client=ec2_client,
            availability_zone="us-west-2a",
        )

        self.assertEqual(
            PriceQuote(
                purchase_mode="spot",
                current_price_per_hour="0.0123",
                spot_price_limit="0.10",
                availability_zone="us-west-2a",
                source="spot-history",
            ),
            quote,
        )

    def test_on_demand_quote_uses_pricing_client(self) -> None:
        """Expected: on_demand quote uses the pricing client and skips spot lookup."""
        pricing_client = Mock()
        pricing_client.get_products.return_value = {
            "PriceList": [GetOnDemandHourlyPriceTests._price_list_entry("0.0832")]
        }
        ec2_client = Mock()

        quote = lookup_deploy_price_quote(
            purchase_mode="on_demand",
            instance_type="t3.large",
            spot_price_limit=None,
            region="us-west-2",
            ec2_client=ec2_client,
            pricing_client=pricing_client,
        )

        self.assertEqual("on_demand", quote.purchase_mode)
        self.assertEqual("0.0832", quote.current_price_per_hour)
        self.assertEqual("pricing-api", quote.source)
        ec2_client.describe_spot_price_history.assert_not_called()


if __name__ == "__main__":
    unittest.main()
