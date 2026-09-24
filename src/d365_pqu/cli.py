from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from d365_pqu.config import Paths
from d365_pqu.errors import PquError
from d365_pqu.pipeline import (
    build_site,
    heartbeat_due,
    load_json,
    run_sync,
    source_document_from_file,
    verify_artifacts,
)


def _parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _write_github_output(path: str | None, values: dict[str, Any]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            rendered = ("true" if value else "false") if isinstance(value, bool) else str(value)
            handle.write(f"{key}={rendered}\n")


def _result_payload(result: Any) -> dict[str, Any]:
    return {
        "changed": bool(result.changed),
        "status": result.status,
        "source_hash": result.source_hash,
        "source_commit": result.source_commit,
        "record_count": result.record_count,
        "current_count": result.current_count,
        "upcoming_count": result.upcoming_count,
        "warning_count": result.warning_count,
        "error_count": result.error_count,
        "data_dir": result.data_dir,
        "workbook_path": result.workbook_path,
        "site_dir": result.site_dir,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="d365-pqu", description="D365 PQU dataset pipeline")
    parser.add_argument(
        "--root", default=".", help="Repository root containing data, schema, and excel"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser(
        "sync", help="Fetch Microsoft source and update all artifacts"
    )
    sync_parser.add_argument(
        "--source-file", help="Read Markdown from a local file instead of the network"
    )
    sync_parser.add_argument(
        "--source-commit", default="0" * 40, help="Commit value to record for local source files"
    )
    sync_parser.add_argument("--now", help="Override the current UTC timestamp")
    sync_parser.add_argument(
        "--check", action="store_true", help="Validate without writing artifacts"
    )
    sync_parser.add_argument("--github-output", help="Write step outputs to this file")
    sync_parser.add_argument(
        "--build-site", action="store_true", help="Build the Pages site after a successful run"
    )

    verify_parser = subparsers.add_parser(
        "verify", help="Validate committed artifacts without network access"
    )
    verify_parser.add_argument("--github-output", help="Write step outputs to this file")

    site_parser = subparsers.add_parser(
        "build-site", help="Build the Pages site from committed artifacts"
    )
    site_parser.add_argument("--github-output", help="Write step outputs to this file")

    heartbeat_parser = subparsers.add_parser(
        "heartbeat-due", help="Report whether a health heartbeat is due"
    )
    heartbeat_parser.add_argument("--now", help="Override the current UTC timestamp")
    heartbeat_parser.add_argument("--github-output", help="Write step outputs to this file")
    return parser


def command_sync(args: argparse.Namespace, paths: Paths) -> int:
    now = _parse_now(args.now)
    source = None
    if args.source_file:
        source = source_document_from_file(
            Path(args.source_file),
            commit=args.source_commit,
            now=now,
        )
    result = run_sync(
        paths,
        source=source,
        now=now,
        write=not args.check,
    )
    if args.build_site and not args.check:
        build_site(paths)
    payload = _result_payload(result)
    _write_github_output(args.github_output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def command_verify(args: argparse.Namespace, paths: Paths) -> int:
    payload = verify_artifacts(paths)
    _write_github_output(
        args.github_output, {"verified": True, "latest_pqu_id": payload.get("latest_pqu_id", "")}
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def command_build_site(args: argparse.Namespace, paths: Paths) -> int:
    build_site(paths)
    _write_github_output(args.github_output, {"site_dir": str(paths.site_dir)})
    print(json.dumps({"site_dir": str(paths.site_dir)}, indent=2, sort_keys=True))
    return 0


def command_heartbeat_due(args: argparse.Namespace, paths: Paths) -> int:
    now = _parse_now(args.now)
    health = load_json(paths.health_path)
    due = heartbeat_due(health, now)
    _write_github_output(args.github_output, {"heartbeat_due": due})
    print(json.dumps({"heartbeat_due": due}, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(os.environ.get("D365_PQU_ROOT", args.root))
    paths = Paths.from_root(root)
    handlers = {
        "sync": command_sync,
        "verify": command_verify,
        "build-site": command_build_site,
        "heartbeat-due": command_heartbeat_due,
    }
    try:
        return handlers[args.command](args, paths)
    except PquError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
