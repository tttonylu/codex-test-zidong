"""Minimal CLI for NAS management queries and task controls."""

from __future__ import annotations

import argparse
import json
from typing import Any

from shared.protocol import TaskControlPayload
from terminal_agent.adapters import NasControlPlaneClient


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(prog="python -m nas_control_plane.cli")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8765",
        help="NAS control plane base URL",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser("summary", help="Show NAS summary")
    summary_parser.set_defaults(handler=_handle_summary)

    terminals_parser = subparsers.add_parser("terminals", help="List or get terminals")
    terminals_parser.add_argument("--terminal-id", help="Terminal id to fetch")
    terminals_parser.add_argument("--status", help="Filter by terminal status")
    terminals_parser.set_defaults(handler=_handle_terminals)

    instances_parser = subparsers.add_parser("instances", help="List or get instances")
    instances_parser.add_argument("--instance-id", help="Instance id to fetch")
    instances_parser.add_argument("--terminal-id", help="Filter by terminal id")
    instances_parser.add_argument("--runtime-status", help="Filter by runtime status")
    instances_parser.set_defaults(handler=_handle_instances)

    tasks_parser = subparsers.add_parser("tasks", help="List or get tasks")
    tasks_parser.add_argument("--task-id", help="Task id to fetch")
    tasks_parser.add_argument("--terminal-id", help="Filter by terminal id")
    tasks_parser.add_argument("--status", help="Filter by task status")
    tasks_parser.add_argument("--script-name", help="Filter by script name")
    tasks_parser.set_defaults(handler=_handle_tasks)

    task_events_parser = subparsers.add_parser("task-events", help="List task lifecycle events")
    task_events_parser.add_argument("--task-id", help="Task id to filter")
    task_events_parser.set_defaults(handler=_handle_task_events)

    task_attempts_parser = subparsers.add_parser("task-attempts", help="List aggregated task attempts")
    task_attempts_parser.add_argument("--task-id", required=True, help="Task id to inspect")
    task_attempts_parser.set_defaults(handler=_handle_task_attempts)

    task_report_parser = subparsers.add_parser("task-report", help="Show a combined diagnostic report for one task")
    task_report_parser.add_argument("--task-id", required=True, help="Task id to inspect")
    task_report_parser.set_defaults(handler=_handle_task_report)

    logs_parser = subparsers.add_parser("logs", help="List or get logs")
    logs_parser.add_argument("--log-id", help="Log id to fetch")
    logs_parser.add_argument("--terminal-id", help="Filter by terminal id")
    logs_parser.add_argument("--task-id", help="Filter by task id")
    logs_parser.add_argument("--level", help="Filter by log level")
    logs_parser.set_defaults(handler=_handle_logs)

    cancel_parser = subparsers.add_parser("cancel-task", help="Cancel a task")
    cancel_parser.add_argument("--task-id", required=True, help="Task id to cancel")
    cancel_parser.add_argument("--reason", default="cancelled by operator", help="Cancellation reason")
    cancel_parser.add_argument("--requested-by", default="cli", help="Operator identifier")
    cancel_parser.set_defaults(handler=_handle_cancel_task)

    retry_parser = subparsers.add_parser("retry-task", help="Retry a failed task")
    retry_parser.add_argument("--task-id", required=True, help="Task id to retry")
    retry_parser.add_argument("--reason", default="retry requested by operator", help="Retry reason")
    retry_parser.add_argument("--requested-by", default="cli", help="Operator identifier")
    retry_parser.set_defaults(handler=_handle_retry_task)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the NAS CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    client = NasControlPlaneClient(args.base_url)
    payload = args.handler(client, args)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


def _handle_summary(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    del args
    return client.get_summary()


def _handle_terminals(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    if args.terminal_id:
        return client.get_terminal(args.terminal_id)
    return client.list_terminals(status=args.status)


def _handle_instances(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    if args.instance_id:
        return client.get_instance(args.instance_id)
    return client.list_instances(
        terminal_id=args.terminal_id,
        runtime_status=args.runtime_status,
    )


def _handle_tasks(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    if args.task_id:
        return client.get_task(args.task_id)
    return client.list_tasks_filtered(
        terminal_id=args.terminal_id,
        status=args.status,
        script_name=args.script_name,
    )


def _handle_task_events(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.list_task_events(task_id=args.task_id)


def _handle_task_attempts(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.list_task_attempts(task_id=args.task_id)


def _handle_task_report(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.get_task_report(task_id=args.task_id)


def _handle_logs(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    if args.log_id:
        return client.get_log(args.log_id)
    return client.list_logs_filtered(
        terminal_id=args.terminal_id,
        task_id=args.task_id,
        level=args.level,
    )


def _handle_cancel_task(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.control_task(
        TaskControlPayload(
            task_id=args.task_id,
            action="cancel",
            reason=args.reason,
            requested_by=args.requested_by,
        )
    )


def _handle_retry_task(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.control_task(
        TaskControlPayload(
            task_id=args.task_id,
            action="retry",
            reason=args.reason,
            requested_by=args.requested_by,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
