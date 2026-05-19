"""Small NAS management CLI."""

from __future__ import annotations

import argparse
import json
from typing import Any

from terminal_agent.adapters import NasControlPlaneClient

from .views import (
    render_account_summary,
    render_campaign_summary,
    render_collection,
    render_creator_summary,
    render_daily_stat_summary,
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
    terminals.add_argument("--min-active-task-count")
    terminals.add_argument("--max-parallel-tasks")
    terminals.add_argument("--blocked-instance-id")

    terminal = subparsers.add_parser("terminal")
    terminal.add_argument("terminal_id")

    instances = subparsers.add_parser("instances")
    instances.add_argument("--terminal-id")
    instances.add_argument("--runtime-status")

    instance = subparsers.add_parser("instance")
    instance.add_argument("instance_id")

    tasks = subparsers.add_parser("tasks")
    tasks.add_argument("--terminal-id")
    tasks.add_argument("--preferred-terminal-id")
    tasks.add_argument("--dispatch-mode")
    tasks.add_argument("--queue-dispatch-status")
    tasks.add_argument("--queue-dispatch-accepted")
    tasks.add_argument("--status")
    tasks.add_argument("--script-name")
    tasks.add_argument("--retryable")
    tasks.add_argument("--final")
    tasks.add_argument("--wait-reason")
    tasks.add_argument("--blocked-by-instance-id")
    tasks.add_argument("--retry-kind")
    tasks.add_argument("--terminal-affinity")
    tasks.add_argument("--recovery-claim-terminal-id")

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

    plugin_creators = subparsers.add_parser("plugin-creators")

    plugin_accounts = subparsers.add_parser("plugin-accounts")
    plugin_accounts.add_argument("--status")

    plugin_stats = subparsers.add_parser("plugin-stats")
    plugin_stats.add_argument("--stat-date")

    plugin_campaigns = subparsers.add_parser("plugin-campaigns")
    plugin_campaigns.add_argument("--plugin-name")
    plugin_campaigns.add_argument("--status")

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
            min_active_task_count=_parse_int(args.min_active_task_count),
            max_parallel_tasks=_parse_int(args.max_parallel_tasks),
            blocked_instance_id=args.blocked_instance_id,
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
            preferred_terminal_id=args.preferred_terminal_id,
            dispatch_mode=args.dispatch_mode,
            queue_dispatch_status=args.queue_dispatch_status,
            queue_dispatch_accepted=_parse_bool(args.queue_dispatch_accepted),
            status=args.status,
            script_name=args.script_name,
            retryable=_parse_bool(args.retryable),
            final=_parse_bool(args.final),
            wait_reason=args.wait_reason,
            blocked_by_instance_id=args.blocked_by_instance_id,
            retry_kind=args.retry_kind,
            terminal_affinity=args.terminal_affinity,
            recovery_claim_terminal_id=args.recovery_claim_terminal_id,
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

    if args.command == "plugin-creators":
        items = client.list_plugin_creators()["items"]
        print(
            render_collection(
                "Plugin Creators",
                [render_creator_summary(_item_to_namespace(item)) for item in items],
            )
        )
        return 0

    if args.command == "plugin-accounts":
        items = client.list_plugin_accounts(status=args.status)["items"]
        print(
            render_collection(
                "Plugin Accounts",
                [render_account_summary(_item_to_namespace(item)) for item in items],
            )
        )
        return 0

    if args.command == "plugin-stats":
        items = client.list_plugin_daily_stats(stat_date=args.stat_date)["items"]
        print(
            render_collection(
                "Plugin Daily Stats",
                [render_daily_stat_summary(_item_to_namespace(item)) for item in items],
            )
        )
        return 0

    if args.command == "plugin-campaigns":
        items = client.list_plugin_campaigns(
            plugin_name=args.plugin_name,
            status=args.status,
        )["items"]
        print(
            render_collection(
                "Plugin Campaigns",
                [render_campaign_summary(_item_to_namespace(item)) for item in items],
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


def _parse_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    return int(raw)


def _item_to_namespace(payload: dict[str, Any]) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(**payload)


if __name__ == "__main__":
    raise SystemExit(main())
