"""P2 offline tests: S3Sink, S3 config, and the CLI with --sink s3 against an in-memory fake S3."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError

from tests.weather.conftest import build_payload_for_params, build_synthetic_openmeteo_payload

BUCKET = "pharmaflow-dev-weather-raw-123456789012-ap-southeast-1"
ROLE = "arn:aws:iam::123456789012:role/pharmaflow-dev-weather-local-writer"
ENV = {"WEATHER_S3_BUCKET": BUCKET, "WEATHER_S3_ROLE_ARN": ROLE, "WEATHER_S3_REGION": "ap-southeast-1",
       "WEATHER_AWS_PROFILE": "my-aws"}


def _err(code: str, op: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, op)


class _Body(io.BytesIO):
    pass


class _Paginator:
    def __init__(self, fake: "FakeS3") -> None:
        self.fake = fake

    def paginate(self, *, Bucket: str, Prefix: str) -> "_Pages":
        return _Pages([k for k in sorted(self.fake.objects) if k.startswith(Prefix)])


class _Pages:
    def __init__(self, keys: list[str]) -> None:
        self.keys = keys

    def search(self, expr: str) -> Any:
        assert expr == "Contents[].Key"
        return iter(self.keys) if self.keys else iter([None])


class FakeS3:
    """Minimal S3 semantics used by S3Sink: conditional put, checksum check, prefix listing."""

    def __init__(self, deny_codes: dict[str, str] | None = None) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts: list[dict[str, Any]] = []
        self.deny_codes = deny_codes or {}

    def put_object(self, **kw: Any) -> dict[str, Any]:
        assert kw["Bucket"] == BUCKET
        data = kw["Body"]
        expected = base64.b64encode(hashlib.sha256(data).digest()).decode()
        if kw.get("ChecksumSHA256") != expected:
            raise _err("BadDigest", "PutObject")
        if kw.get("IfNoneMatch") == "*" and kw["Key"] in self.objects:
            raise _err("PreconditionFailed", "PutObject")
        self.puts.append(kw)
        self.objects[kw["Key"]] = data
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key in self.deny_codes:
            raise _err(self.deny_codes[Key], "GetObject")
        if Key not in self.objects:
            raise _err("NoSuchKey", "GetObject")
        return {"Body": _Body(self.objects[Key])}

    def list_objects_v2(self, *, Bucket: str, Prefix: str, MaxKeys: int = 1000) -> dict[str, Any]:
        keys = [k for k in sorted(self.objects) if k.startswith(Prefix)][:MaxKeys]
        resp: dict[str, Any] = {"KeyCount": len(keys)}
        if keys:
            resp["Contents"] = [{"Key": k} for k in keys]
        return resp

    def get_paginator(self, name: str) -> _Paginator:
        assert name == "list_objects_v2"
        return _Paginator(self)

    def get_bucket_location(self, *, Bucket: str) -> dict[str, Any]:
        return {"LocationConstraint": "ap-southeast-1"}


def _sink(fake: FakeS3 | None = None) -> Any:
    from src.weather.storage import S3Sink

    return S3Sink(bucket=BUCKET, client=fake or FakeS3(), region="ap-southeast-1")


KEY = "raw/open_meteo/weather_forecast/ingest_date=2026-11-12/run_id=r/tasks/t/attempts/a/response.json"


# ------------------------------------------------------------------- S3Sink


def test_s3_sink_roundtrip_exact_bytes_with_checksum() -> None:
    fake = FakeS3()
    sink = _sink(fake)
    body = build_synthetic_openmeteo_payload(hours=24, days=1)
    sink.put_bytes(KEY, body)
    assert sink.get_bytes(KEY) == body
    assert fake.puts[0]["ChecksumSHA256"] == base64.b64encode(hashlib.sha256(body).digest()).decode()
    assert fake.puts[0]["ContentType"] == "application/json" and "IfNoneMatch" not in fake.puts[0]
    assert sink.exists(KEY) and not sink.exists(KEY[:-5])  # exact key match, not prefix
    assert sink.uri(KEY) == f"s3://{BUCKET}/{KEY}"


def test_s3_sink_put_if_absent_never_overwrites() -> None:
    sink = _sink()
    key = KEY.replace("attempts/a/response.json", "accepted.json")
    assert sink.put_json_if_absent(key, {"attempt_id": "a1"}) is True
    assert sink.put_json_if_absent(key, {"attempt_id": "a2"}) is False
    assert sink.get_json(key)["attempt_id"] == "a1"


def test_s3_sink_conflict_is_retried_once() -> None:
    fake = FakeS3()
    calls = {"n": 0}
    original = fake.put_object

    def flaky(**kw: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _err("ConditionalRequestConflict", "PutObject")
        return original(**kw)

    fake.put_object = flaky  # type: ignore[method-assign]
    assert _sink(fake).put_json_if_absent(KEY, {"x": 1}) is True and calls["n"] == 2


@pytest.mark.parametrize("key", ["raw/other/x.json", "../raw/open_meteo/weather_forecast/x", "tmp/x.json",
                                 "raw/open_meteo/weather_forecast_evil/x.json"])
def test_s3_sink_rejects_keys_outside_weather_prefixes(key: str) -> None:
    with pytest.raises(ValueError):
        _sink().put_bytes(key, b"x")


def test_s3_sink_missing_key_is_file_not_found_but_access_denied_propagates() -> None:
    sink = _sink(FakeS3(deny_codes={KEY: "AccessDenied"}))
    with pytest.raises(FileNotFoundError):
        sink.get_bytes(KEY.replace("response", "metadata"))
    with pytest.raises(ClientError):
        sink.get_bytes(KEY)


def test_s3_sink_list_keys_under_prefix() -> None:
    sink = _sink()
    base = "raw/open_meteo/historical_weather/ingest_date=2026-11-12/run_id=r"
    assert sink.list_keys(f"{base}/summary") == []
    sink.put_json(f"{base}/summary/abc.json", {"x": 1})
    sink.put_json(f"{base}/plan.json", {"x": 1})
    assert sink.list_keys(f"{base}/summary") == [f"{base}/summary/abc.json"]


# ------------------------------------------------------------------- config


def test_load_s3_config_validates_and_defaults_region() -> None:
    from src.weather.aws_session import S3ConfigError, load_s3_config

    cfg = load_s3_config({"WEATHER_S3_BUCKET": BUCKET, "WEATHER_S3_ROLE_ARN": ROLE})
    assert cfg.region == "ap-southeast-1" and cfg.profile is None and cfg.account_id == "123456789012"
    with pytest.raises(S3ConfigError, match="WEATHER_S3_ROLE_ARN"):
        load_s3_config({"WEATHER_S3_BUCKET": BUCKET})
    with pytest.raises(S3ConfigError, match="role ARN"):
        load_s3_config({"WEATHER_S3_BUCKET": BUCKET, "WEATHER_S3_ROLE_ARN": "arn:aws:iam::123456789012:user/x"})


def test_session_name_is_valid_for_sts() -> None:
    import re

    from src.weather.aws_session import build_session_name

    name = build_session_name()
    assert 2 <= len(name) <= 64 and re.fullmatch(r"[\w+=,.@-]+", name)


class _FakeSTS:
    def __init__(self, arn: str) -> None:
        self.arn = arn
        self.assumed: dict[str, Any] = {}

    def assume_role(self, **kw: Any) -> dict[str, Any]:
        self.assumed = kw
        return {"Credentials": {"AccessKeyId": "ASIAFAKE", "SecretAccessKey": "SECRETFAKE", "SessionToken": "TOK",
                                "Expiration": datetime(2026, 11, 12, 1, 0, tzinfo=timezone.utc)}}

    def get_caller_identity(self) -> dict[str, Any]:
        return {"Arn": self.arn, "Account": "123456789012"}


def test_assume_writer_session_checks_identity_and_hides_secrets(monkeypatch: Any) -> None:
    import boto3

    from src.weather.aws_session import S3ConfigError, assume_writer_session, load_s3_config

    cfg = load_s3_config(ENV)
    good = _FakeSTS("arn:aws:sts::123456789012:assumed-role/pharmaflow-dev-weather-local-writer/sess")

    class _Base:
        def client(self, name: str, **kw: Any) -> Any:
            return good

    monkeypatch.setattr(boto3.Session, "client", lambda self, name, **kw: good)
    _, info = assume_writer_session(cfg, base_session=_Base())
    assert good.assumed["RoleArn"] == ROLE and good.assumed["DurationSeconds"] == 3600
    assert "SECRETFAKE" not in json.dumps(info) and info["expires_at_utc"] == "2026-11-12T01:00:00Z"

    bad = _FakeSTS("arn:aws:iam::123456789012:user/admin")
    monkeypatch.setattr(boto3.Session, "client", lambda self, name, **kw: bad)

    class _BadBase:
        def client(self, name: str, **kw: Any) -> Any:
            return bad

    with pytest.raises(S3ConfigError, match="not the writer role"):
        assume_writer_session(cfg, base_session=_BadBase())


# ---------------------------------------------------------------- CLI e2e s3

NOW = datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc)


def _fake_om(calls: list[str]) -> Any:
    def fetch(endpoint_key: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append(endpoint_key)
        days = int(params["forecast_days"]) if "forecast_days" in params else (
            datetime.fromisoformat(params["end_date"]) - datetime.fromisoformat(params["start_date"])).days + 1
        body = build_payload_for_params(params, now_utc=NOW)
        return {"http_status": 200, "raw_bytes": body, "raw_sha256": hashlib.sha256(body).hexdigest(),
                "rate_limit_headers": {"X-RateLimit-Cost": "4.0"}, "headers": {}}
    return fetch


def _cli(argv: list[str], tmp_path: Path, rows: Any, fake: FakeS3, calls: list[str]) -> tuple[int, Any]:
    from src.weather.cli import run_cli

    factory = lambda cfg: (fake, {"assumed_arn": f"arn:aws:sts::123456789012:assumed-role/x/s",  # noqa: E731
                                  "expires_at_utc": "2026-11-11T04:00:00Z"})
    return run_cli(argv, store_rows_override=rows, runtime_dir=tmp_path, fetcher=_fake_om(calls),
                   sleep=lambda s: None, now_utc=NOW, s3_factory=factory, s3_env=ENV)


def test_cli_s3_backfill_cross_2022_plan_run_resume_status(tmp_path: Path, pilot_store_rows: list[dict]) -> None:
    fake, calls = FakeS3(), []
    code, plan = _cli(["plan", "backfill", "--start-date", "2021-12-25", "--end-date", "2022-01-05",
                       "--location-ids", "516", "--request-id", "p2", "--sink", "s3"], tmp_path, pilot_store_rows,
                      fake, calls)
    assert code == 0, plan
    run_prefix = f"raw/open_meteo/historical_weather/ingest_date=2026-11-11/run_id={plan['run_id']}"
    assert plan["plan_s3_key"] == f"{run_prefix}/plan.json" and plan["plan_s3_key"] in fake.objects

    code, run = _cli(["run", "--plan", plan["plan_s3_key"], "--sink", "s3"], tmp_path, pilot_store_rows, fake, calls)
    assert code == 0 and run["run_status"] == "SUCCEEDED" and run["http_calls"] == 2
    assert run["plan_uri"] == f"s3://{BUCKET}/{plan['plan_s3_key']}"
    accepted = sorted(k for k in fake.objects if k.endswith("accepted.json"))
    assert len(accepted) == 2
    assert accepted[0].startswith("raw/open_meteo/historical_forecast/") and accepted[1].startswith(run_prefix)
    for key in accepted:
        marker = json.loads(fake.objects[key])
        assert hashlib.sha256(fake.objects[marker["response_key"]]).hexdigest() == marker["raw_sha256"]
        assert marker["storage"] == {"kind": "s3", "bucket": BUCKET, "region": "ap-southeast-1"}
    n_objects = len(fake.objects)

    code, resume = _cli(["resume", "--run-id", plan["run_id"], "--sink", "s3"], tmp_path, pilot_store_rows, fake,
                        calls)
    assert code == 0 and resume["http_calls"] == 0 and len(calls) == 2 and len(fake.objects) == n_objects

    code, status = _cli(["status", "--run-id", plan["run_id"], "--sink", "s3"], tmp_path, [], fake, calls)
    assert code == 0 and status["run_status"] == "SUCCEEDED" and len(status["summary_keys"]) == 1

    # State is per sink: the same run_id is unknown to --sink local, and local files were not written.
    code, local = _cli(["status", "--run-id", plan["run_id"]], tmp_path, [], fake, calls)
    assert code == 1 and "not registered" in local["error"]
    assert not (tmp_path / "raw").exists()
    assert (tmp_path / "state" / "s3" / BUCKET / "runs" / f"{plan['run_id']}.json").is_file()


def test_cli_s3_preflight_reports_identity_and_bucket(tmp_path: Path, pilot_store_rows: list[dict]) -> None:
    code, out = _cli(["preflight", "--sink", "s3"], tmp_path, pilot_store_rows, FakeS3(), [])
    assert code == 0, out
    s3 = out["checks"]["s3"]
    assert s3["ok"] and s3["bucket_region"] == "ap-southeast-1" and len(s3["list_prefixes"]) == 3
    assert "Secret" not in json.dumps(out)


def test_cli_s3_dry_run_writes_nothing(tmp_path: Path, pilot_store_rows: list[dict]) -> None:
    fake = FakeS3()
    code, out = _cli(["plan", "daily", "--cohort", "pilot", "--location-ids", "516", "--dry-run", "--sink", "s3"],
                     tmp_path, pilot_store_rows, fake, [])
    assert code == 0 and out["dry_run"] is True and fake.objects == {}
    assert list(tmp_path.rglob("*.json")) == []
