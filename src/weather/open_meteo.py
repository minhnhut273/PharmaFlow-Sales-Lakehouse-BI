"""HTTPS client restricted to the three allowlisted Open-Meteo endpoints."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from src.weather import __version__

ENDPOINTS: dict[str, str] = {
    "forecast": "https://api.open-meteo.com/v1/forecast",
    "historical_forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "historical_weather": "https://archive-api.open-meteo.com/v1/archive",
}

FIXED_UNITS = {"temperature_unit": "celsius", "wind_speed_unit": "ms", "precipitation_unit": "mm"}
USER_AGENT = f"PharmaFlow-WeatherIngestion/{__version__} (DACN student project; non-commercial)"
KEPT_HEADERS = ("Retry-After", "Content-Type", "Content-Encoding", "Date")
# (connect, read) seconds. ERA5 archive requests are noticeably slower than forecast requests.
DEFAULT_TIMEOUTS: dict[str, tuple[float, float]] = {
    "forecast": (10.0, 30.0),
    "historical_forecast": (10.0, 60.0),
    "historical_weather": (10.0, 90.0),
}


def resolve_endpoint_url(endpoint_key: str) -> str:
    """Map an endpoint key to its allowlisted URL; anything else (including raw URLs) is rejected."""
    try:
        return ENDPOINTS[endpoint_key]
    except (KeyError, TypeError):
        raise ValueError(f"Endpoint {endpoint_key!r} is not in the Open-Meteo allowlist {sorted(ENDPOINTS)}") from None


def build_open_meteo_params(
    *,
    endpoint_key: str,
    latitude: float,
    longitude: float,
    timezone_name: str,
    hourly_variables: Sequence[str],
    daily_variables: Sequence[str],
    forecast_days: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    resolve_endpoint_url(endpoint_key)
    params: dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone_name,
        "timeformat": "unixtime",
        **FIXED_UNITS,
    }
    if hourly_variables:
        params["hourly"] = ",".join(hourly_variables)
    if daily_variables:
        params["daily"] = ",".join(daily_variables)

    if endpoint_key == "forecast":
        if forecast_days is None or start_date or end_date:
            raise ValueError("forecast endpoint requires forecast_days and no start/end dates")
        params["forecast_days"] = int(forecast_days)
    else:
        if forecast_days is not None or not start_date or not end_date:
            raise ValueError(f"{endpoint_key} requires start_date and end_date and no forecast_days")
        params["start_date"] = start_date
        params["end_date"] = end_date

    if model is not None:
        if endpoint_key == "historical_weather":
            raise ValueError("archive-api (ERA5) must not receive a models parameter")
        params["models"] = model
    return params


def _pick_headers(headers: Mapping[str, Any], *, rate_limit: bool) -> dict[str, str]:
    out: dict[str, str] = {}
    wanted = {h.lower(): h for h in KEPT_HEADERS}
    for name, value in dict(headers or {}).items():
        lower = str(name).lower()
        if rate_limit and lower.startswith("x-ratelimit-"):
            canonical = "X-RateLimit-" + "-".join(p.capitalize() for p in lower[len("x-ratelimit-"):].split("-"))
            out[canonical] = str(value)
        elif not rate_limit and lower in wanted:
            out[wanted[lower]] = str(value)
    return out


def _default_session() -> Any:
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session


def fetch_open_meteo(
    *,
    endpoint_key: str,
    params: Mapping[str, Any],
    session: Any = None,
    timeout: float | tuple[float, float] | None = None,
) -> dict[str, Any]:
    """GET an allowlisted endpoint without following redirects; keep the exact decoded body bytes."""
    url = resolve_endpoint_url(endpoint_key)
    sess = session if session is not None else _default_session()
    effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUTS[endpoint_key]
    resp = sess.get(url, params=dict(params), timeout=effective_timeout, allow_redirects=False)
    raw = resp.content if resp.content is not None else b""
    return {
        "endpoint_key": endpoint_key,
        "endpoint": url,
        "http_status": int(resp.status_code),
        "raw_bytes": raw,
        "raw_byte_length": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "rate_limit_headers": _pick_headers(resp.headers, rate_limit=True),
        "headers": _pick_headers(resp.headers, rate_limit=False),
    }


def classify_http_response(*, http_status: int, headers: Mapping[str, str] | None = None) -> dict[str, Any]:
    hdrs = {str(k).lower(): v for k, v in dict(headers or {}).items()}
    if http_status == 200:
        return {"category": "OK", "http_status": http_status}
    if http_status == 429:
        retry_after: int | None = None
        raw = hdrs.get("retry-after")
        if raw is not None:
            try:
                retry_after = max(0, int(float(str(raw).strip())))
            except ValueError:
                retry_after = None
        return {"category": "DEFERRED_RATE_LIMIT", "http_status": http_status, "retry_after_seconds": retry_after}
    if 500 <= http_status <= 599:
        return {"category": "RETRYABLE_SERVER_ERROR", "http_status": http_status}
    # 3xx (redirects are never followed) and other 4xx are terminal.
    return {"category": "TERMINAL_CLIENT_ERROR", "http_status": http_status}
