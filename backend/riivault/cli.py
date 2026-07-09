"""riivault console entrypoint (``riivault <command>``)."""

from __future__ import annotations

import argparse
import asyncio
import logging

from .config import get_settings


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="riivault", description="riivault backend CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("collect-once", help="Run one incremental Reddit collection pass")
    sub.add_parser("collect-hn", help="Run one incremental Hacker News collection pass")
    sub.add_parser("collect-gh", help="Run one incremental GitHub Issues collection pass")
    sub.add_parser("collect-ph", help="Run one incremental Product Hunt collection pass")
    sub.add_parser("collect-adoption", help="Collect adoption metrics (stars/releases/downloads/SE questions)")
    sub.add_parser("aggregate", help="Recompute derived aggregates from raw_* (idempotent)")
    sub.add_parser("purge", help="Purge expired/deleted raw content (compliance)")
    sub.add_parser("publish-issue", help="Publish/refresh this week's issue")
    sub.add_parser("scheduler", help="Run the APScheduler loop")
    sub.add_parser("seed-demo", help="Seed demo data into derived tables + weekly_issue")
    api_p = sub.add_parser("api", help="Run the FastAPI server via uvicorn")
    api_p.add_argument("--host", default="0.0.0.0")
    api_p.add_argument("--port", type=int, default=8000)
    api_p.add_argument("--reload", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging()
    settings = get_settings()

    if args.command == "collect-once":
        from .collector.pipeline import collect_once

        asyncio.run(collect_once(settings))
    elif args.command == "collect-hn":
        from .collector.hackernews import collect_once_hn

        asyncio.run(collect_once_hn(settings))
    elif args.command == "collect-gh":
        from .collector.github import collect_once_gh

        asyncio.run(collect_once_gh(settings))
    elif args.command == "collect-ph":
        from .collector.producthunt import collect_once_ph

        asyncio.run(collect_once_ph(settings))
    elif args.command == "collect-adoption":
        from .collector.adoption import collect_once_adoption

        asyncio.run(collect_once_adoption(settings))
    elif args.command == "aggregate":
        from .collector.aggregate import (
            run_aggregate,
            run_aggregate_gh,
            run_aggregate_hn,
            run_aggregate_ph,
        )

        asyncio.run(run_aggregate(settings))
        asyncio.run(run_aggregate_hn(settings))
        asyncio.run(run_aggregate_gh(settings))
        asyncio.run(run_aggregate_ph(settings))
    elif args.command == "purge":
        from .collector.purge import run_purge

        asyncio.run(run_purge(settings))
    elif args.command == "publish-issue":
        from .collector.publish import publish_issue

        asyncio.run(publish_issue(settings))
    elif args.command == "seed-demo":
        from .collector.seed_demo import seed_demo

        asyncio.run(seed_demo(settings))
    elif args.command == "scheduler":
        from .collector.scheduler import run_scheduler

        try:
            asyncio.run(run_scheduler(settings))
        except (KeyboardInterrupt, SystemExit):
            pass
    elif args.command == "api":
        import uvicorn

        uvicorn.run(
            "riivault.api.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
