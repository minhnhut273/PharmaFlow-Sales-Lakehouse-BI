"""AWS session for the S3 sink: base profile (aws login) -> sts:AssumeRole on the writer role."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

ENV_BUCKET = "WEATHER_S3_BUCKET"
ENV_REGION = "WEATHER_S3_REGION"
ENV_ROLE_ARN = "WEATHER_S3_ROLE_ARN"
ENV_PROFILE = "WEATHER_AWS_PROFILE"
DEFAULT_REGION = "ap-southeast-1"
SESSION_SECONDS = 3600

_ROLE_ARN = re.compile(r"^arn:aws:iam::(\d{12}):role/[A-Za-z0-9+=,.@_/-]+$")
_BUCKET = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


class S3ConfigError(ValueError):
    """Missing or invalid S3 runtime configuration."""


@dataclass(frozen=True)
class S3Config:
    bucket: str
    region: str
    role_arn: str
    profile: str | None

    @property
    def account_id(self) -> str:
        return _ROLE_ARN.match(self.role_arn).group(1)  # type: ignore[union-attr]


def load_s3_config(env: Mapping[str, str] | None = None) -> S3Config:
    src = os.environ if env is None else env
    missing = [k for k in (ENV_BUCKET, ENV_ROLE_ARN) if not src.get(k)]
    if missing:
        raise S3ConfigError(f"Missing S3 settings: {', '.join(missing)} (set them in .env)")
    bucket, role_arn = src[ENV_BUCKET].strip(), src[ENV_ROLE_ARN].strip()
    if not _BUCKET.match(bucket):
        raise S3ConfigError(f"{ENV_BUCKET} is not a valid bucket name")
    if not _ROLE_ARN.match(role_arn):
        raise S3ConfigError(f"{ENV_ROLE_ARN} must be an IAM role ARN")
    region = (src.get(ENV_REGION) or DEFAULT_REGION).strip()
    profile = (src.get(ENV_PROFILE) or "").strip() or None
    return S3Config(bucket=bucket, region=region, role_arn=role_arn, profile=profile)


def build_session_name(prefix: str = "pharmaflow-weather-cli") -> str:
    """RoleSessionName: 2-64 chars of [\\w+=,.@-]; shows up in CloudTrail."""
    import getpass
    import uuid

    user = re.sub(r"[^\w+=,.@-]", "-", getpass.getuser() or "user")[:20]
    return f"{prefix}-{user}-{uuid.uuid4().hex[:8]}"[:64]


def assume_writer_session(config: S3Config, *, base_session: Any = None) -> tuple[Any, dict[str, str]]:
    """Return (boto3.Session with temporary role credentials, identity info). Never returns secrets."""
    import boto3

    base = base_session or boto3.Session(profile_name=config.profile, region_name=config.region)
    sts = base.client("sts", region_name=config.region)
    resp = sts.assume_role(
        RoleArn=config.role_arn, RoleSessionName=build_session_name(), DurationSeconds=SESSION_SECONDS
    )
    creds = resp["Credentials"]
    session = boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=config.region,
    )
    ident = session.client("sts", region_name=config.region).get_caller_identity()
    role_name = config.role_arn.rsplit("/", 1)[-1]
    expected = f"arn:aws:sts::{config.account_id}:assumed-role/{role_name}/"
    if not str(ident["Arn"]).startswith(expected):
        raise S3ConfigError(f"Assumed identity {ident['Arn']} is not the writer role {config.role_arn}")
    return session, {
        "assumed_arn": ident["Arn"],
        "account": ident["Account"],
        "expires_at_utc": creds["Expiration"].strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
