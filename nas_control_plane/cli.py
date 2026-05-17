"""Small NAS management CLI."""

from __future__ import annotations

import argparse
import json
from typing import Any

from terminal_agent.adapters import NasControlPlaneClient

from .views import (
    render_collection,
    render_instance_summary,
    render_log_summary,
    render_task_summary,
    render_terminal_summary,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the NAS CLI parser."""

    parser = argparse.ArgumentParser(prog="nas-control")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    subparsers = parser.add_subparsers(dest="command", required=True)

    terminals = subparsers.add_parser("terminals")
    terminals.add_argument("--status")
    terminals.add_argument("--operator-name")

    terminal = subparsers.add_parser("terminal")
    terminal.add_argument("terminal_id")

    instances = subparsers.add_parser("instances")
    instances.add_argument("--terminal-id")
    instances.add_argument("--runtime-status")

    instance = subparsers.add_parser("instance")
    instance.add_argument("instance_id")

    tasks = subparsers.add_parser("tasks")
    tasks.add_argument("--terminal-id")
    tasks.add_argument("--status")
    tasks.add_argument("--script-name")
    tasks.add_argument("--retryable")
    tasks.add_argument("--final")

    task = subparsers.add_parser("task")
    task.add_argument("task_id")

    retry = subparsers.add_parser("retry")
    retry.add_argument("task_id")
    retry.add_argument("--requested-by", default="cli")

    cancel = subparsers.add_parser("cancel")
    cancel.add_argument("task_id")
    cancel.add_argument("--requested-by", default="cli")

    logs = subparsers.add_parser("logs")
    logs.add_argument("--terminal-id")
    logs.add_argument("--task-id")
    logs.add_argument("--level")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and print a text view."""

    parser = build_parser()
    args = parser.parse_args(argv)
    client = NasControlPlaneClient(args.base_url)

    if args.command == "terminals":
        items = client.list_terminals(
            status=args.status,
            operator_name=args.operator_name,
        )["items"]
        print(
            render_collection(
                "Terminals",
                [render_terminal_summary(_item_to_namespace(item)) for item in items],
            )
        )
        return 0

    if args.command == "terminal":
        print(render_terminal_summary(_item_to_namespace(client.get_terminal(args.terminal_id))))
        return 0

    if args.command == "instances":
        items = client.list_instances(
            terminal_id=args.terminal_id,
            runtime_status=args.runtime_status,
        )["items"]
        print(
            render_collection(
                "Instances",
                [render_instance_summary(_item_to_namespace(item)) for item in items],
            )
        )
        return 0

    if args.command == "instance":
        print(render_instance_summary(_item_to_namespace(client.get_instance(args.instance_id))))
        return 0

    if args.command == "tasks":
        items = client.query_tasks(
            terminal_id=args.terminal_id,
            status=args.status,
            script_name=args.script_name,
            retryable=_parse_bool(args.retryable),
            final=_parse_bool(args.final),
        )["items"]
        print(
            render_collection(
                "Tasks",
                [render_task_summary(_item_to_namespace(item)) for item in items],
            )
        )
        return 0

    if args.command == "task":
        print(render_task_summary(_item_to_namespace(client.get_task(args.task_id))))
        return 0

    if args.command == "retry":
        print(render_task_summary(_item_to_namespace(client.retry_task(args.task_id, requested_by=args.requested_by))))
        return 0

    if args.command == "cancel":
        print(render_task_summary(_item_to_namespace(client.cancel_task(args.task_id, requested_by=args.requested_by))))
        return 0

    if args.command == "logs":
        items = client.query_logs(
            terminal_id=args.terminal_id,
            task_id=args.task_id,
            level=args.level,
        )["items"]
        print(
            render_collection(
                "Logs",
                [render_log_summary(_item_to_namespace(item)) for item in items],
            )
        )
        return 0

    return 1


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {raw}")


def _item_to_namespace(payload: dict[str, Any]) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(**payload)


if __name__ == "__main__":
    raise SystemExit(main())
