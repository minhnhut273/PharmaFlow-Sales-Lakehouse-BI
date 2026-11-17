"""Offline unit tests for Gold MD-01 reconciliation logic."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from src.ops.publish_md01 import reconcile_grouped_aggregates  # noqa: E402


def test_reconcile_grouped_aggregates_passes_with_null_currency() -> None:
    silver = [
        {
            "sales_uom_code": "IRPD_UOM_tab_7508386a",
            "currency_code": "IDR",
            "provenance_class": "OBSERVED",
            "row_count": 274477,
            "total_qty": Decimal("512345.000000"),
            "total_amount": Decimal("12345678.5000"),
        },
        {
            "sales_uom_code": "SIM_PHARMA_SALES_UNIT",
            "currency_code": None,
            "provenance_class": "SYNTHETIC",
            "row_count": 25534,
            "total_qty": Decimal("99100.250000"),
            "total_amount": Decimal("0"),
        },
    ]
    gold = [
        {
            "sales_uom_code": "IRPD_UOM_tab_7508386a",
            "currency_code": "IDR",
            "provenance_class": "OBSERVED",
            "row_count": 274477,
            "total_qty": Decimal("512345.000000"),
            "total_amount": Decimal("12345678.5000"),
        },
        {
            "sales_uom_code": "SIM_PHARMA_SALES_UNIT",
            "currency_code": None,
            "provenance_class": "SYNTHETIC",
            "row_count": 25534,
            "total_qty": Decimal("99100.250000"),
            "total_amount": Decimal("0"),
        },
    ]
    assert (
        reconcile_grouped_aggregates(
            silver,
            gold,
            key_fields=("sales_uom_code", "currency_code", "provenance_class"),
        )
        == []
    )


def test_reconcile_grouped_aggregates_flags_qty_and_missing_group() -> None:
    silver = [
        {
            "sales_uom_code": "ONYX_UNIT",
            "currency_code": "EUR",
            "provenance_class": "SYNTHETIC",
            "row_count": 62036,
            "total_qty": Decimal("1000.0000"),
            "total_amount": Decimal("5000.00"),
        },
        {
            "sales_uom_code": "SIM_PHARMA_SALES_UNIT",
            "currency_code": None,
            "provenance_class": "SYNTHETIC",
            "row_count": 10,
            "total_qty": Decimal("10.0000"),
            "total_amount": Decimal("0"),
        },
    ]
    gold = [
        {
            "sales_uom_code": "ONYX_UNIT",
            "currency_code": "EUR",
            "provenance_class": "SYNTHETIC",
            "row_count": 62036,
            "total_qty": Decimal("999.0000"),
            "total_amount": Decimal("5000.00"),
        }
    ]
    mismatches = reconcile_grouped_aggregates(
        silver,
        gold,
        key_fields=("sales_uom_code", "currency_code", "provenance_class"),
    )
    assert len(mismatches) == 2
    assert mismatches[0]["reason"] == "aggregate_mismatch"
    assert mismatches[1]["reason"] == "missing_group"
    assert mismatches[1]["silver_present"] is True
    assert mismatches[1]["gold_present"] is False
