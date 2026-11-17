from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from source_db import (
    TARGET_DATABASE,
    apply_migration,
    backup_previous_database,
    bootstrap_schema,
    database_report,
    load_source,
    verify_all,
    verify_snapshot_record,
    verify_source,
)
from source_prepare import SOURCE_ORDER, prepare_sample, prepare_source


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare, load, and verify PharmaFlow forecast-source datasets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Profile and prepare all rows for one source.")
    prepare.add_argument("source", choices=SOURCE_ORDER)

    sample = subparsers.add_parser("prepare-sample", help="Create a deterministic validation sample.")
    sample.add_argument("source", choices=SOURCE_ORDER)

    subparsers.add_parser("backup", help="Check the retained archive; refuses to reconnect to the deleted previous database.")

    migration = subparsers.add_parser("migrate", help="Apply an allowlisted versioned migration to the v2 target database.")
    migration.add_argument("migration", choices=("20261104_02_product_packaging_pair_fk",))
    migration.add_argument("--database", default=TARGET_DATABASE, choices=(TARGET_DATABASE,))

    bootstrap = subparsers.add_parser("bootstrap", help="Apply schema_full.sql to the empty active target database.")
    bootstrap.add_argument("--database", default=TARGET_DATABASE, choices=(TARGET_DATABASE,))

    load = subparsers.add_parser("load", help="Load one prepared sample or full source.")
    load.add_argument("source", choices=SOURCE_ORDER)
    load.add_argument("mode", choices=("sample", "full"))
    load.add_argument("--database", default=TARGET_DATABASE, choices=(TARGET_DATABASE,))

    verify = subparsers.add_parser("verify", help="Reconcile one source or all completed sources.")
    verify.add_argument("source", nargs="?", choices=(*SOURCE_ORDER, "all"))
    verify.add_argument("mode", nargs="?", choices=("sample", "full"), default="full")
    verify.add_argument("--database", default=TARGET_DATABASE, choices=(TARGET_DATABASE,))

    report = subparsers.add_parser("report", help="Write a database row-count report.")
    report.add_argument("--database", default=TARGET_DATABASE, choices=(TARGET_DATABASE,))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "backup":
            _print(backup_previous_database())
        elif args.command == "migrate":
            _print(apply_migration(args.migration, args.database))
        elif args.command == "prepare":
            _print(prepare_source(args.source))
        elif args.command == "prepare-sample":
            _print(prepare_sample(args.source))
        elif args.command == "bootstrap":
            verify_snapshot_record()
            _print(bootstrap_schema(args.database))
        elif args.command == "load":
            _print(load_source(args.source, args.mode, args.database))
        elif args.command == "verify":
            if args.source == "all":
                _print(verify_all(args.database))
            elif args.source is None:
                raise ValueError("Specify a source or 'all'.")
            else:
                _print(verify_source(args.source, args.mode, args.database))
        elif args.command == "report":
            _print(database_report(args.database))
        return 0
    except Exception as exc:
        print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
