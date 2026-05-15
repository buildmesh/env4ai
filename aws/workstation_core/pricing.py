"""Pricing helpers for workstation purchase modes (spot and on-demand)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from typing import Any

LOGGER = logging.getLogger(__name__)
_PRICING_API_REGION = "us-east-1"


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """Hourly price information for one workstation purchase mode.

    Args:
        purchase_mode: ``spot`` or ``on_demand``.
        current_price_per_hour: Latest observed hourly price, as a USD string.
        spot_price_limit: Spot Fleet max price cap from the environment spec.
        availability_zone: AZ used for the spot price lookup, when known.
        source: Short label for the price source (``spot-history`` or ``pricing-api``).
    """

    purchase_mode: str
    current_price_per_hour: str | None = None
    spot_price_limit: str | None = None
    availability_zone: str | None = None
    source: str | None = None


def format_price_per_hour(price: str | None) -> str:
    """Format a USD hourly price string as ``$X.XXXX/hr`` for display."""
    if price is None:
        return "—"
    cleaned = price.strip()
    if not cleaned:
        return "—"
    try:
        value = float(cleaned)
    except ValueError:
        return cleaned
    return f"${value:.4f}/hr"


def get_current_spot_price(
    ec2_client: Any,
    *,
    instance_type: str,
    availability_zone: str | None = None,
    product_description: str = "Linux/UNIX",
) -> str | None:
    """Return the most recent spot price for an instance type, or ``None`` on miss.

    Args:
        ec2_client: Boto3 EC2 client.
        instance_type: EC2 instance type (for example ``t3.large``).
        availability_zone: Optional AZ for a more specific lookup.
        product_description: AWS product description filter.

    Returns:
        Price as a USD string (for example ``"0.0234"``), or ``None`` if
        no price was returned or the API call failed.
    """
    if not instance_type or not instance_type.strip():
        return None
    kwargs: dict[str, Any] = {
        "InstanceTypes": [instance_type.strip()],
        "ProductDescriptions": [product_description],
        "StartTime": datetime.now(timezone.utc),
        "MaxResults": 1,
    }
    if availability_zone and availability_zone.strip():
        kwargs["AvailabilityZone"] = availability_zone.strip()
    try:
        response = ec2_client.describe_spot_price_history(**kwargs)
    except Exception as err:  # noqa: BLE001
        LOGGER.warning("describe_spot_price_history failed: %s", err)
        return None
    history = response.get("SpotPriceHistory", [])
    if not history:
        return None
    price = str(history[0].get("SpotPrice", "")).strip()
    return price or None


def get_on_demand_hourly_price(
    pricing_client: Any,
    *,
    instance_type: str,
    region: str,
    operating_system: str = "Linux",
    tenancy: str = "Shared",
) -> str | None:
    """Return the on-demand hourly price for an instance type, or ``None`` on miss.

    Args:
        pricing_client: Boto3 pricing client (must target ``us-east-1`` or another
            region where the AWS Pricing API is available).
        instance_type: EC2 instance type.
        region: Target deployment region code (for example ``us-west-2``).
        operating_system: Pricing API ``operatingSystem`` filter value.
        tenancy: Pricing API ``tenancy`` filter value.

    Returns:
        Price as a USD string (for example ``"0.0832"``), or ``None`` when the
        lookup fails or returns no usable price dimension.
    """
    if not instance_type or not instance_type.strip():
        return None
    if not region or not region.strip():
        return None
    filters = [
        {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region.strip()},
        {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type.strip()},
        {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": operating_system},
        {"Type": "TERM_MATCH", "Field": "tenancy", "Value": tenancy},
        {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
        {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
    ]
    try:
        response = pricing_client.get_products(
            ServiceCode="AmazonEC2",
            Filters=filters,
            MaxResults=1,
        )
    except Exception as err:  # noqa: BLE001
        LOGGER.warning("pricing get_products failed: %s", err)
        return None
    price_list = response.get("PriceList", [])
    if not price_list:
        return None
    return _extract_on_demand_price(price_list[0])


def _extract_on_demand_price(price_list_entry: str | dict[str, Any]) -> str | None:
    """Extract the OnDemand USD price-per-unit from a pricing API payload."""
    try:
        item = (
            json.loads(price_list_entry)
            if isinstance(price_list_entry, str)
            else price_list_entry
        )
    except json.JSONDecodeError as err:
        LOGGER.warning("Failed to parse pricing payload: %s", err)
        return None
    terms = item.get("terms", {}).get("OnDemand", {}) if isinstance(item, dict) else {}
    for offer in terms.values():
        for dimension in offer.get("priceDimensions", {}).values():
            price = str(dimension.get("pricePerUnit", {}).get("USD", "")).strip()
            if price:
                return price
    return None


def lookup_deploy_price_quote(
    *,
    purchase_mode: str,
    instance_type: str,
    spot_price_limit: str | None,
    region: str,
    ec2_client: Any | None = None,
    pricing_client: Any | None = None,
    availability_zone: str | None = None,
) -> PriceQuote:
    """Resolve a price quote for the deploy summary or status render.

    Spot lookups use ``describe_spot_price_history`` when an EC2 client is
    provided. On-demand lookups use the Pricing API when a pricing client is
    provided. Either client may be omitted to skip that lookup.
    """
    if purchase_mode not in {"spot", "on_demand"}:
        return PriceQuote(purchase_mode=purchase_mode)
    if purchase_mode == "spot":
        current = (
            get_current_spot_price(
                ec2_client,
                instance_type=instance_type,
                availability_zone=availability_zone,
            )
            if ec2_client is not None
            else None
        )
        return PriceQuote(
            purchase_mode="spot",
            current_price_per_hour=current,
            spot_price_limit=spot_price_limit,
            availability_zone=availability_zone,
            source="spot-history" if current else None,
        )
    current = (
        get_on_demand_hourly_price(
            pricing_client,
            instance_type=instance_type,
            region=region,
        )
        if pricing_client is not None
        else None
    )
    return PriceQuote(
        purchase_mode="on_demand",
        current_price_per_hour=current,
        source="pricing-api" if current else None,
    )
