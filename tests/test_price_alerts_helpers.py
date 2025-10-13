"""Unit tests for price alert helper logic."""

from decimal import Decimal

from app.api.v1.alerts import _should_trigger
from app.db.models import PriceAlertDirection


def test_should_trigger_above_threshold() -> None:
    assert _should_trigger(
        PriceAlertDirection.ABOVE,
        target=Decimal("100"),
        current=Decimal("100"),
    )
    assert _should_trigger(
        PriceAlertDirection.ABOVE,
        target=Decimal("100"),
        current=Decimal("125.50"),
    )
    assert not _should_trigger(
        PriceAlertDirection.ABOVE,
        target=Decimal("100"),
        current=Decimal("99.99"),
    )


def test_should_trigger_below_threshold() -> None:
    assert _should_trigger(
        PriceAlertDirection.BELOW,
        target=Decimal("250"),
        current=Decimal("200"),
    )
    assert _should_trigger(
        PriceAlertDirection.BELOW,
        target=Decimal("250"),
        current=Decimal("250"),
    )
    assert not _should_trigger(
        PriceAlertDirection.BELOW,
        target=Decimal("250"),
        current=Decimal("251"),
    )
