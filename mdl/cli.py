"""Command line entry point: ``python -m mdl.cli``."""

from __future__ import annotations

import argparse
import json
import sys

from .agent import ResearchAgent
from .config import load_settings
from .errors import MdlError
from .logging_store import ResearchStore
from .ollama_client import OllamaClient
from .orchestrator import ToolOrchestrator


def _build(settings):
    store = ResearchStore(settings.db_path, settings.jsonl_path)
    client = OllamaClient(settings)
    orchestrator = ToolOrchestrator(settings.tool_timeout_s)
    agent = ResearchAgent(settings, client, orchestrator, store)
    return agent, client, store


def _summary(outcome) -> dict:
    return {
        "experiment_id": outcome.experiment_id,
        "status": outcome.status,
        "hypothesis": outcome.hypothesis.statement,
        "expression": outcome.tool_request.arguments.expression,
        "expanded": (
            outcome.tool_result.expanded if outcome.tool_result else None
        ),
        "verification": (
            outcome.verification.to_dict() if outcome.verification else None
        ),
        "conclusion": (
            outcome.interpretation.conclusion
            if outcome.interpretation
            else None
        ),
        "uncertainties": (
            outcome.interpretation.uncertainties
            if outcome.interpretation
            else None
        ),
        "rejection": outcome.rejection,
        "latency_ms": round(outcome.latency_ms, 1),
        "token_usage": outcome.token_usage,
    }


def _cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    settings.ensure_data_dir()
    agent, client, store = _build(settings)
    try:
        outcome = agent.run(args.seed, allow_repair=not args.no_repair)
        summary = _summary(outcome)
        if args.json:
            print(json.dumps(summary, ensure_ascii=True, indent=2))
        else:
            print(f"experiment : {summary['experiment_id']}")
            print(f"status     : {summary['status']}")
            print(f"hypothesis : {summary['hypothesis']}")
            print(f"expression : {summary['expression']}")
            print(f"expanded   : {summary['expanded']}")
            if summary["verification"]:
                print(
                    "verification: "
                    f"{summary['verification']['status']} "
                    f"({summary['verification']['method']})"
                )
            print(f"conclusion : {summary['conclusion']}")
            print(f"latency_ms : {summary['latency_ms']}")
            print(f"tokens     : {summary['token_usage']}")
            print(f"sqlite     : {settings.db_path}")
            print(f"jsonl      : {settings.jsonl_path}")
        return 0 if outcome.status == "completed" else 1
    finally:
        client.close()
        store.close()


def _cmd_verify_log(_: argparse.Namespace) -> int:
    settings = load_settings()
    store = ResearchStore(settings.db_path, settings.jsonl_path)
    try:
        report = store.verify_jsonl()
    finally:
        store.close()
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


def _cmd_model_info(_: argparse.Namespace) -> int:
    settings = load_settings()
    client = OllamaClient(settings)
    try:
        info = client.model_info()
    finally:
        client.close()
    if info is None:
        print(f"model {settings.model!r} not found", file=sys.stderr)
        return 1
    print(json.dumps(info, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdl", description="Mathematical Discovery Lab - Block 1"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one complete research loop")
    run.add_argument("--seed", default=None, help="research seed / hypothesis hint")
    run.add_argument(
        "--no-repair",
        action="store_true",
        help="reject an invalid tool request instead of asking the model to repair it",
    )
    run.add_argument("--json", action="store_true", help="print a JSON summary")
    run.set_defaults(func=_cmd_run)

    verify = sub.add_parser("verify-log", help="verify the JSONL hash chain")
    verify.set_defaults(func=_cmd_verify_log)

    info = sub.add_parser("model-info", help="show local Ollama model metadata")
    info.set_defaults(func=_cmd_model_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except MdlError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
