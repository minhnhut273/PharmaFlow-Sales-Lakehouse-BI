"""P4: WINDOW_MISMATCH guard. A response whose local dates differ from the task window is never accepted.

Live evidence (2026-11-13, SDD 7.4): a plan labelled 2026-11-14 received /v1/forecast data starting
2026-11-13 because the forecast endpoint only takes forecast_days and always starts "today".
"""

from __future__ import annotations

import hashlib
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from tests.weather.conftest import build_synthetic_openmeteo_payload


def _payload(start: str, days: int, tz: str, **kw: Any) -> bytes:
    from datetime import date

    epoch = int(datetime.combine(date.fromisoformat(start), time(0, 0), tzinfo=ZoneInfo(tz)).timestamp())
    return build_synthetic_openmeteo_payload(start_epoch=epoch, hours=days * 24, days=days, timezone_name=tz, **kw)


def _validate(raw: bytes, *, start: str | None, end: str, days: int, tz: str, today: str = "2026-11-13") -> Any:
    from src.weather.validation import validate_open_meteo_response

    return validate_open_meteo_response(raw_bytes=raw, expected_days=days, timezone_name=tz, start_date=start,
                                        end_date=end, today_vn=today)


def test_forecast_labelled_next_day_is_rejected() -> None:
    """The exact P4 case: plan 2026-11-14..29, provider returned 2026-11-13..28."""
    raw = _payload("2026-11-13", 16, "Asia/Ho_Chi_Minh")
    r = _validate(raw, start="2026-11-14", end="2026-11-29", days=16, tz="Asia/Ho_Chi_Minh")
    assert r["status"] == "FAILED_VALIDATION" and r["is_accepted"] is False and r["is_terminal"] is True
    assert r["reason"].startswith("WINDOW_MISMATCH") and "2026-11-13..2026-11-28" in r["reason"]
    assert r["returned_window"] == {"start_date": "2026-11-13", "end_date": "2026-11-28"}


def test_matching_window_is_accepted_and_reported() -> None:
    raw = _payload("2026-11-13", 16, "Asia/Ho_Chi_Minh")
    r = _validate(raw, start="2026-11-13", end="2026-11-28", days=16, tz="Asia/Ho_Chi_Minh")
    assert r["status"] == "SUCCEEDED" and r["returned_window"] == {"start_date": "2026-11-13", "end_date": "2026-11-28"}


@pytest.mark.parametrize("tz", ["Europe/Berlin", "Europe/Belgrade", "Asia/Jakarta", "Asia/Ho_Chi_Minh"])
def test_window_uses_store_local_dates(tz: str) -> None:
    raw = _payload("2026-11-13", 2, tz)
    assert _validate(raw, start="2026-11-13", end="2026-11-14", days=2, tz=tz)["is_accepted"] is True
    # Same bytes interpreted for a window one day later must fail.
    assert _validate(raw, start="2026-11-14", end="2026-11-15", days=2, tz=tz)["reason"].startswith("WINDOW_MISMATCH")


def test_backfill_shifted_by_one_hour_is_rejected() -> None:
    """Right step count, but the series starts at 01:00 local: the last hour spills into the next day."""
    from datetime import date

    tz = "Asia/Ho_Chi_Minh"
    epoch = int(datetime.combine(date(2025, 5, 1), time(1, 0), tzinfo=ZoneInfo(tz)).timestamp())
    raw = build_synthetic_openmeteo_payload(start_epoch=epoch, hours=48, days=2, timezone_name=tz)
    r = _validate(raw, start="2025-05-01", end="2025-05-02", days=2, tz=tz)
    assert r["reason"] == "WINDOW_MISMATCH: expected 2025-05-01..2025-05-02, returned 2025-05-01..2025-05-03"


def test_dst_fallback_window_still_matches() -> None:
    """Berlin 2026-10-25 has 25 local hours; a 5-day window starting at local midnight must still match."""
    from datetime import date, timedelta

    tz = ZoneInfo("Europe/Berlin")
    start = datetime.combine(date(2026, 10, 23), time(0, 0), tzinfo=tz)
    raw = build_synthetic_openmeteo_payload(start_epoch=int(start.timestamp()), hours=120, days=5,
                                            timezone_name="Europe/Berlin", utc_offset_seconds=3600)
    end = (start.astimezone(timezone.utc) + timedelta(hours=119)).astimezone(tz).date().isoformat()
    r = _validate(raw, start="2026-10-23", end=end, days=5, tz="Europe/Berlin")
    assert r["is_accepted"] is True and r["non_24h_days"].get("2026-10-25") == 25


def test_validation_without_start_date_keeps_previous_behaviour() -> None:
    raw = _payload("2026-11-13", 2, "Asia/Ho_Chi_Minh")
    assert _validate(raw, start=None, end="2030-01-01", days=2, tz="Asia/Ho_Chi_Minh")["is_accepted"] is True


def test_worker_never_writes_accepted_for_window_mismatch(tmp_path: Path) -> None:
    from src.weather.planner import accepted_key_for, task_base_key
    from src.weather.storage import LocalSink
    from src.weather.worker import execute_task

    raw = _payload("2026-11-13", 16, "Asia/Ho_Chi_Minh")
    task = {
        "run_id": "daily-20261114-sim", "task_id": "taskwindow000001", "ingest_date": "2026-11-14",
        "mode": "daily_forecast", "endpoint_key": "forecast", "s3_prefix": "raw/open_meteo/weather_forecast",
        "store_id": 516, "store_code": "LC:80439", "latitude": 10.746925, "longitude": 106.672734,
        "timezone_name": "Asia/Ho_Chi_Minh", "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        "start_date": "2026-11-14", "end_date": "2026-11-29", "expected_days": 16,
        "contract_version": "weather_variables_v1", "model": "gfs_global", "estimated_cost": 5.6,
    }
    fetch = lambda ek, p: {"http_status": 200, "raw_bytes": raw, "raw_sha256": hashlib.sha256(raw).hexdigest(),  # noqa: E731
                           "rate_limit_headers": {}, "headers": {}}
    sink = LocalSink(tmp_path)
    out = execute_task(task=task, sink=sink, fetcher=fetch, attempt_id="a1", today_vn="2026-11-13")
    assert out["status"] == "FAILED_VALIDATION" and out["validation_reason"].startswith("WINDOW_MISMATCH")
    assert not sink.exists(accepted_key_for(task))
    meta = sink.get_json(f"{task_base_key(task)}/attempts/a1/metadata.json")
    assert meta["returned_window"] == {"start_date": "2026-11-13", "end_date": "2026-11-28"}
    assert sink.exists(f"{task_base_key(task)}/attempts/a1/response.json")  # evidence kept


def test_archive_fixed_offset_dst_window_matches() -> None:
    """Historical archive API uses fixed standard-time utc_offset_seconds (no DST shifts).

    For Europe/Belgrade in summer 2016 (2016-05-19..2016-06-01), Open-Meteo returns utc_offset_seconds=3600
    starting at 1463612400 (2016-05-19 00:00:00+01:00). ZoneInfo CEST would spill 1h to 2016-06-02, but
    evaluating with utc_offset_seconds aligns with 2016-05-19..2016-06-01.
    """
    start_epoch = 1463612400  # 2016-05-18 23:00:00 UTC = 2016-05-19 00:00:00+01:00
    raw = build_synthetic_openmeteo_payload(
        start_epoch=start_epoch,
        hours=14 * 24,
        days=14,
        timezone_name="Europe/Belgrade",
        utc_offset_seconds=3600,
    )
    r = _validate(raw, start="2016-05-19", end="2016-06-01", days=14, tz="Europe/Belgrade")
    assert r["status"] == "SUCCEEDED"
    assert r["is_accepted"] is True
    assert r["returned_window"] == {"start_date": "2016-05-19", "end_date": "2016-06-01"}

