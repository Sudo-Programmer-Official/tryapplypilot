from __future__ import annotations

import argparse
import asyncio
import json
from typing import Sequence

from app.market_scout import MarketScoutAgent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the AI Job Radar Market Scout Agent.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("run-once", help="Execute one collection and notification cycle.")
    subcommands.add_parser("run-loop", help="Run the scout loop continuously using the configured cadence.")
    return parser


async def _run_async(command: str) -> int:
    agent = MarketScoutAgent()
    if command == "run-once":
        summary = await agent.run_once()
        print(json.dumps(summary.to_dict(), indent=2))
        return 0
    if command == "run-loop":
        await agent.run_loop()
        return 0
    raise RuntimeError(f"Unknown command: {command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run_async(args.command))


if __name__ == "__main__":
    raise SystemExit(main())
