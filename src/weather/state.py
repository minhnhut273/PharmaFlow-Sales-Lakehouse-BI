"""Control state. P1-P2: LocalStateStore (JSON files). P3: DynamoStateStore (one DynamoDB table)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TERMINAL_TASK_STATUSES = frozenset(
    {"SUCCEEDED", "ACCEPTED_WITH_WARNINGS", "FAILED_VALIDATION", "FAILED", "EXPIRED", "DLQ"}
)
SUCCESS_TASK_STATUSES = frozenset({"SUCCEEDED", "ACCEPTED_WITH_WARNINGS"})


def _safe(name: str) -> str:
    if not name or any(c in name for c in '/\\:*?"<>|') or name in (".", ".."):
        raise ValueError(f"Unsafe state identifier: {name!r}")
    return name


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LocalStateStore:
    """JSON-file state: runs/<run_id>.json, tasks/<run_id>/<task_id>.json, budget/<date>.json."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir)

    # ------------------------------------------------------------ file io
    def _read(self, path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def _task_path(self, run_id: str, task_id: str) -> Path:
        return self.root_dir / "tasks" / _safe(run_id) / f"{_safe(task_id)}.json"

    # ------------------------------------------------------------- leases
    def acquire_task_lease(
        self, *, run_id: str, task_id: str, worker_id: str, now_epoch: int, lease_seconds: int = 120
    ) -> bool:
        path = self._task_path(run_id, task_id)
        rec = self._read(path) or {"run_id": run_id, "task_id": task_id, "attempt_count": 0}
        owner, expires = rec.get("lease_owner"), rec.get("lease_expires_at")
        if owner and owner != worker_id and expires is not None and now_epoch < int(expires):
            return False
        rec["lease_owner"] = worker_id
        rec["lease_expires_at"] = int(now_epoch) + int(lease_seconds)
        self._write(path, rec)
        return True

    def release_task_lease(self, *, run_id: str, task_id: str, worker_id: str) -> None:
        path = self._task_path(run_id, task_id)
        rec = self._read(path)
        if rec and rec.get("lease_owner") == worker_id:
            rec["lease_owner"] = None
            rec["lease_expires_at"] = None
            self._write(path, rec)

    # ------------------------------------------------------------- status
    def record_task_status(self, run_id: str, task_id: str, status: str, **details: Any) -> dict[str, Any]:
        path = self._task_path(run_id, task_id)
        rec = self._read(path) or {"run_id": run_id, "task_id": task_id, "attempt_count": 0}
        rec["status"] = status
        rec["updated_at_utc"] = _now_iso()
        if details.pop("count_attempt", False):
            rec["attempt_count"] = int(rec.get("attempt_count", 0)) + 1
        for key, value in details.items():
            rec[key] = value
        self._write(path, rec)
        return rec

    def get_task(self, run_id: str, task_id: str) -> dict[str, Any] | None:
        return self._read(self._task_path(run_id, task_id))

    def get_task_statuses(self, run_id: str) -> dict[str, str]:
        folder = self.root_dir / "tasks" / _safe(run_id)
        if not folder.is_dir():
            return {}
        out: dict[str, str] = {}
        for path in sorted(folder.glob("*.json")):
            rec = self._read(path) or {}
            if rec.get("status"):
                out[rec["task_id"]] = rec["status"]
        return out

    # ------------------------------------------------------------- budget
    def _budget_path(self, date_vn: str) -> Path:
        return self.root_dir / "budget" / f"{_safe(date_vn)}.json"

    def get_budget(self, date_vn: str) -> dict[str, float]:
        rec = self._read(self._budget_path(date_vn)) or {}
        return {"used_daily": float(rec.get("used_daily", 0.0)), "used_backfill": float(rec.get("used_backfill", 0.0))}

    def _hour_path(self, hour_key: str) -> Path:
        return self.root_dir / "hour" / f"{_safe(hour_key)}.json"

    def get_hour_usage(self, hour_key: str) -> float:
        rec = self._read(self._hour_path(hour_key)) or {}
        return float(rec.get("units", 0.0))

    def add_hour_usage(self, hour_key: str, units: float) -> float:
        new_units = round(self.get_hour_usage(hour_key) + float(units), 6)
        self._write(self._hour_path(hour_key), {"hour_key": hour_key, "units": new_units, "updated_at_utc": _now_iso()})
        return new_units

    def add_usage(self, date_vn: str, mode: str, units: float) -> dict[str, float]:
        rec = self.get_budget(date_vn)
        key = "used_daily" if mode == "daily_forecast" else "used_backfill"
        rec[key] = round(rec[key] + float(units), 6)
        self._write(self._budget_path(date_vn), {"date_vn": date_vn, **rec, "updated_at_utc": _now_iso()})
        return rec

    def reserve_units(
        self,
        *,
        date_vn: str,
        minute_key: str,
        mode: str,
        units: float,
        hour_key: str | None = None,
        hourly_limit: float | None = None,
    ) -> dict[str, Any]:
        """Pre-charge daily (and optional hourly) budget. The local CLI paces minutes by sleep."""
        from src.weather.limiter import HOURLY_SAFE_LIMIT, check_budget_admission

        limit_hr = HOURLY_SAFE_LIMIT if hourly_limit is None else float(hourly_limit)
        if hour_key is not None and self.get_hour_usage(hour_key) + float(units) > limit_hr + 1e-9:
            return {"allowed": False, "reason": "HOURLY_LIMIT"}
        admission = check_budget_admission(mode=mode, required_units=float(units), **self.get_budget(date_vn))
        if admission["allowed"]:
            self.add_usage(date_vn, mode, units)
            if hour_key is not None:
                self.add_hour_usage(hour_key, units)
        return {"allowed": bool(admission["allowed"]), "reason": admission["reason"]}

    def adjust_usage(self, *, date_vn: str, mode: str, delta: float, hour_key: str | None = None) -> None:
        if delta:
            self.add_usage(date_vn, mode, delta)
            if hour_key is not None:
                self.add_hour_usage(hour_key, delta)

    # --------------------------------------------------------------- runs
    def register_run(self, run_id: str, plan_key: str, mode: str, **details: Any) -> dict[str, Any]:
        path = self.root_dir / "runs" / f"{_safe(run_id)}.json"
        rec = self._read(path) or {"run_id": run_id, "registered_at_utc": _now_iso()}
        rec.update({"plan_key": plan_key, "mode": mode, **details})
        self._write(path, rec)
        return rec

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._read(self.root_dir / "runs" / f"{_safe(run_id)}.json")


# ===================================================================== DynamoDB

ACTIVE_INDEX = "active_runs"
ACTIVE_FLAG = "ACTIVE"
MINUTE_UNIT_LIMIT = 550.0  # below Open-Meteo's 600/min to leave headroom for header rounding
HOURLY_UNIT_LIMIT = 4980.0  # below Open-Meteo's 5000/h to leave headroom for header rounding
BUDGET_TTL_SECONDS = 35 * 86400
HOUR_TTL_SECONDS = 2 * 86400
RATE_TTL_SECONDS = 86400


def _num(value: float) -> dict[str, str]:
    from decimal import Decimal

    number = round(float(value), 6)
    if number == int(number):
        return {"N": str(int(number))}
    return {"N": str(Decimal(str(number)))}


class DynamoStateStore:
    """Same interface as LocalStateStore, backed by one PAY_PER_REQUEST table (pk/sk).

    RUN#<run_id> / META           run registry; gsi1pk = "ACTIVE" while not terminal
    RUN#<run_id> / TASK#<task_id> task status, lease, attempt_count
    BUDGET#<YYYY-MM-DD> / META    used_total, used_daily, used_backfill (daily quota, VN date)
    RATE#<YYYYMMDDHHMM> / META    units (per-minute Open-Meteo weight)
    """

    def __init__(self, *, table: str, client: Any, now_epoch: Any = None) -> None:
        import time

        from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

        self.table = table
        self.client = client
        self._ser = TypeSerializer()
        self._de = TypeDeserializer()
        self._now = now_epoch or (lambda: int(time.time()))

    # ----------------------------------------------------------- helpers
    @staticmethod
    def _run_key(run_id: str) -> dict[str, Any]:
        return {"pk": {"S": f"RUN#{run_id}"}, "sk": {"S": "META"}}

    @staticmethod
    def _task_key(run_id: str, task_id: str) -> dict[str, Any]:
        return {"pk": {"S": f"RUN#{run_id}"}, "sk": {"S": f"TASK#{task_id}"}}

    def _value(self, value: Any) -> dict[str, Any]:
        from decimal import Decimal

        if isinstance(value, float):
            value = Decimal(str(value))
        elif isinstance(value, dict):
            value = {k: (Decimal(str(v)) if isinstance(v, float) else v) for k, v in value.items()}
        return self._ser.serialize(value)

    def _item(self, raw: dict[str, Any] | None) -> dict[str, Any] | None:
        if not raw:
            return None
        from decimal import Decimal

        out = {}
        for k, v in raw.items():
            val = self._de.deserialize(v)
            if isinstance(val, Decimal):
                val = int(val) if val == val.to_integral_value() else float(val)
            out[k] = val
        return out

    @staticmethod
    def _code(exc: Exception) -> str:
        return str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))

    def _update(self, key: dict[str, Any], sets: dict[str, Any], *, add: dict[str, float] | None = None,
                remove: tuple[str, ...] = (), condition: str | None = None,
                cond_values: dict[str, Any] | None = None, if_not_exists: tuple[str, ...] = ()) -> None:
        names: dict[str, str] = {}
        values: dict[str, Any] = {}
        parts_set, parts_add, parts_rm = [], [], []
        for i, (k, v) in enumerate(sets.items()):
            names[f"#s{i}"] = k
            values[f":s{i}"] = self._value(v)
            expr = f"if_not_exists(#s{i}, :s{i})" if k in if_not_exists else f":s{i}"
            parts_set.append(f"#s{i} = {expr}")
        for i, (k, v) in enumerate((add or {}).items()):
            names[f"#a{i}"] = k
            values[f":a{i}"] = _num(v)
            parts_add.append(f"#a{i} :a{i}")
        for i, k in enumerate(remove):
            names[f"#r{i}"] = k
            parts_rm.append(f"#r{i}")
        expr = " ".join(p for p in (
            ("SET " + ", ".join(parts_set)) if parts_set else "",
            ("ADD " + ", ".join(parts_add)) if parts_add else "",
            ("REMOVE " + ", ".join(parts_rm)) if parts_rm else "",
        ) if p)
        kwargs: dict[str, Any] = {"TableName": self.table, "Key": key, "UpdateExpression": expr,
                                  "ExpressionAttributeNames": names}
        if condition:
            kwargs["ConditionExpression"] = condition
            names.update({k: v for k, v in (cond_values or {}).items() if k.startswith("#")})
            values.update({k: v for k, v in (cond_values or {}).items() if k.startswith(":")})
        if values:
            kwargs["ExpressionAttributeValues"] = values
        self.client.update_item(**kwargs)

    # ------------------------------------------------------------- leases
    def acquire_task_lease(
        self, *, run_id: str, task_id: str, worker_id: str, now_epoch: int, lease_seconds: int = 120
    ) -> bool:
        try:
            self._update(
                self._task_key(run_id, task_id),
                {"lease_owner": worker_id, "lease_expires_at": int(now_epoch) + int(lease_seconds),
                 "run_id": run_id, "task_id": task_id},
                condition="attribute_not_exists(#lo) OR #lo = :w OR #le <= :now",
                cond_values={"#lo": "lease_owner", "#le": "lease_expires_at",
                             ":w": {"S": worker_id}, ":now": _num(int(now_epoch))},
            )
        except Exception as exc:
            if self._code(exc) == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def release_task_lease(self, *, run_id: str, task_id: str, worker_id: str) -> None:
        try:
            self._update(self._task_key(run_id, task_id), {}, remove=("lease_owner", "lease_expires_at"),
                         condition="#lo = :w", cond_values={"#lo": "lease_owner", ":w": {"S": worker_id}})
        except Exception as exc:
            if self._code(exc) != "ConditionalCheckFailedException":
                raise

    def clear_expired_lease(self, *, run_id: str, task_id: str, now_epoch: int) -> bool:
        try:
            self._update(self._task_key(run_id, task_id), {}, remove=("lease_owner", "lease_expires_at"),
                         condition="#le <= :now", cond_values={"#le": "lease_expires_at", ":now": _num(now_epoch)})
        except Exception as exc:
            if self._code(exc) == "ConditionalCheckFailedException":
                return False
            raise
        return True

    # ------------------------------------------------------------- status
    def record_task_status(self, run_id: str, task_id: str, status: str, **details: Any) -> dict[str, Any]:
        count = bool(details.pop("count_attempt", False))
        sets = {"status": status, "updated_at_utc": _now_iso(), "run_id": run_id, "task_id": task_id}
        sets.update({k: v for k, v in details.items() if v is not None})
        self._update(self._task_key(run_id, task_id), sets, add={"attempt_count": 1} if count else None)
        return {"run_id": run_id, "task_id": task_id, "status": status}

    def seed_task(self, run_id: str, task_id: str, **fields: Any) -> None:
        """Create the TASK item as PLANNED without overwriting any existing status (replay-safe)."""
        sets = {"status": "PLANNED", "run_id": run_id, "task_id": task_id,
                **{k: v for k, v in fields.items() if v is not None}}
        self._update(self._task_key(run_id, task_id), sets, if_not_exists=("status",))

    def get_task(self, run_id: str, task_id: str) -> dict[str, Any] | None:
        resp = self.client.get_item(TableName=self.table, Key=self._task_key(run_id, task_id), ConsistentRead=True)
        return self._item(resp.get("Item"))

    def get_task_statuses(self, run_id: str) -> dict[str, str]:
        out: dict[str, str] = {}
        pages = self.client.get_paginator("query").paginate(
            TableName=self.table, ConsistentRead=True,
            KeyConditionExpression="pk = :pk AND begins_with(sk, :t)",
            ExpressionAttributeValues={":pk": {"S": f"RUN#{run_id}"}, ":t": {"S": "TASK#"}},
        )
        for page in pages:
            for raw in page.get("Items", []):
                item = self._item(raw) or {}
                if item.get("status"):
                    out[item["sk"][len("TASK#"):]] = item["status"]
        return out

    def list_tasks(self, run_id: str) -> list[dict[str, Any]]:
        out = []
        pages = self.client.get_paginator("query").paginate(
            TableName=self.table, ConsistentRead=True,
            KeyConditionExpression="pk = :pk AND begins_with(sk, :t)",
            ExpressionAttributeValues={":pk": {"S": f"RUN#{run_id}"}, ":t": {"S": "TASK#"}},
        )
        for page in pages:
            out.extend(self._item(raw) for raw in page.get("Items", []))
        return out

    # ------------------------------------------------------------- budget
    def get_budget(self, date_vn: str) -> dict[str, float]:
        resp = self.client.get_item(TableName=self.table, ConsistentRead=True,
                                    Key={"pk": {"S": f"BUDGET#{date_vn}"}, "sk": {"S": "META"}})
        item = self._item(resp.get("Item")) or {}
        return {"used_daily": float(item.get("used_daily", 0.0)), "used_backfill": float(item.get("used_backfill", 0.0))}

    def reserve_units(self, *, date_vn: str, minute_key: str, mode: str, units: float,
                      hour_key: str | None = None,
                      daily_limit: float | None = None, daily_reserve: float | None = None,
                      minute_limit: float = MINUTE_UNIT_LIMIT,
                      hourly_limit: float = HOURLY_UNIT_LIMIT) -> dict[str, Any]:
        """Atomically charge the daily, minute, and (optionally) hourly windows (TransactWriteItems)."""
        from src.weather.limiter import DEFAULT_DAILY_LIMIT, DEFAULT_DAILY_RESERVE

        limit = DEFAULT_DAILY_LIMIT if daily_limit is None else daily_limit
        reserve = DEFAULT_DAILY_RESERVE if daily_reserve is None else daily_reserve
        u = float(units)
        mode_attr = "used_daily" if mode == "daily_forecast" else "used_backfill"
        now = self._now()
        budget_cond = "(attribute_not_exists(#tot) OR #tot <= :maxtot)"
        budget_vals: dict[str, Any] = {":u": _num(u), ":maxtot": _num(limit - u), ":ttl": _num(now + BUDGET_TTL_SECONDS)}
        names = {"#tot": "used_total", "#m": mode_attr, "#ttl": "expires_at"}
        if mode != "daily_forecast":
            budget_cond += " AND (attribute_not_exists(#bf) OR #bf <= :maxbf)"
            names["#bf"] = "used_backfill"
            budget_vals[":maxbf"] = _num(limit - reserve - u)
        items = [
            {"Update": {
                "TableName": self.table,
                "Key": {"pk": {"S": f"BUDGET#{date_vn}"}, "sk": {"S": "META"}},
                "UpdateExpression": "ADD #tot :u, #m :u SET #ttl = if_not_exists(#ttl, :ttl)",
                "ConditionExpression": budget_cond,
                "ExpressionAttributeNames": names,
                "ExpressionAttributeValues": budget_vals,
            }},
            {"Update": {
                "TableName": self.table,
                "Key": {"pk": {"S": f"RATE#{minute_key}"}, "sk": {"S": "META"}},
                "UpdateExpression": "ADD #un :u SET #ttl = if_not_exists(#ttl, :ttl)",
                "ConditionExpression": "attribute_not_exists(#un) OR #un <= :maxmin",
                "ExpressionAttributeNames": {"#un": "units", "#ttl": "expires_at"},
                "ExpressionAttributeValues": {":u": _num(u), ":maxmin": _num(minute_limit - u),
                                              ":ttl": _num(now + RATE_TTL_SECONDS)},
            }},
        ]
        if hour_key is not None:
            items.append({"Update": {
                "TableName": self.table,
                "Key": {"pk": {"S": f"HOUR#{hour_key}"}, "sk": {"S": "META"}},
                "UpdateExpression": "ADD #un :u SET #ttl = if_not_exists(#ttl, :ttl)",
                "ConditionExpression": "attribute_not_exists(#un) OR #un <= :maxhr",
                "ExpressionAttributeNames": {"#un": "units", "#ttl": "expires_at"},
                "ExpressionAttributeValues": {":u": _num(u), ":maxhr": _num(hourly_limit - u),
                                              ":ttl": _num(now + HOUR_TTL_SECONDS)},
            }})
        try:
            self.client.transact_write_items(TransactItems=items)
        except Exception as exc:
            if self._code(exc) != "TransactionCanceledException":
                raise
            reasons = [r.get("Code") for r in getattr(exc, "response", {}).get("CancellationReasons", [])]
            if reasons and reasons[0] == "ConditionalCheckFailed":
                return {"allowed": False, "reason": "BUDGET_EXCEEDED_FOR_RUN"}
            if len(reasons) > 1 and reasons[1] == "ConditionalCheckFailed":
                return {"allowed": False, "reason": "MINUTE_LIMIT"}
            if len(reasons) > 2 and reasons[2] == "ConditionalCheckFailed":
                return {"allowed": False, "reason": "HOURLY_LIMIT"}
            raise
        return {"allowed": True, "reason": "OK"}

    def adjust_usage(self, *, date_vn: str, mode: str, delta: float, hour_key: str | None = None) -> None:
        if not delta:
            return
        mode_attr = "used_daily" if mode == "daily_forecast" else "used_backfill"
        self._update({"pk": {"S": f"BUDGET#{date_vn}"}, "sk": {"S": "META"}}, {},
                     add={"used_total": delta, mode_attr: delta})
        if hour_key is not None:
            self._update({"pk": {"S": f"HOUR#{hour_key}"}, "sk": {"S": "META"}}, {},
                         add={"units": delta})

    def add_usage(self, date_vn: str, mode: str, units: float) -> dict[str, float]:
        self.adjust_usage(date_vn=date_vn, mode=mode, delta=units)
        return self.get_budget(date_vn)

    # --------------------------------------------------------------- runs
    def register_run(self, run_id: str, plan_key: str, mode: str, **details: Any) -> dict[str, Any]:
        sets = {"run_id": run_id, "plan_key": plan_key, "mode": mode, "gsi1pk": ACTIVE_FLAG,
                "registered_at_utc": _now_iso(), **{k: v for k, v in details.items() if v is not None}}
        self._update(self._run_key(run_id), sets, if_not_exists=("registered_at_utc",))
        return {"run_id": run_id, "plan_key": plan_key, "mode": mode, **details}

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        resp = self.client.get_item(TableName=self.table, Key=self._run_key(run_id), ConsistentRead=True)
        return self._item(resp.get("Item"))

    def list_active_runs(self) -> list[dict[str, Any]]:
        out = []
        pages = self.client.get_paginator("query").paginate(
            TableName=self.table, IndexName=ACTIVE_INDEX,
            KeyConditionExpression="gsi1pk = :a", ExpressionAttributeValues={":a": {"S": ACTIVE_FLAG}},
        )
        for page in pages:
            out.extend(self._item(raw) for raw in page.get("Items", []))
        return out

    def mark_run_terminal(self, run_id: str, *, run_status: str, summary_key: str | None) -> None:
        self._update(self._run_key(run_id),
                     {"run_status": run_status, "terminal_summary_key": summary_key, "terminal_at_utc": _now_iso()},
                     remove=("gsi1pk",))
