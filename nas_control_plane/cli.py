"""Minimal CLI for NAS management queries and task controls."""

from __future__ import annotations

import argparse
import json
from typing import Any

from nas_control_plane.services import build_chat_task_payload, build_follow_task_payload, build_probe_task_payload
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
    task_report_parser.add_argument("--raw", action="store_true", help="Print the full JSON report")
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

    create_follow_parser = subparsers.add_parser("create-follow-task", help="Create a standardized follow task")
    _add_standard_task_options(create_follow_parser)
    create_follow_parser.add_argument("--target-handle", required=True, help="Target handle for the follow task")
    create_follow_parser.set_defaults(handler=_handle_create_follow_task)

    create_chat_parser = subparsers.add_parser("create-chat-task", help="Create a standardized chat task")
    _add_standard_task_options(create_chat_parser)
    create_chat_parser.add_argument("--target-handle", required=True, help="Target handle for the chat task")
    create_chat_parser.set_defaults(handler=_handle_create_chat_task)

    create_probe_parser = subparsers.add_parser("create-probe-task", help="Create a standardized probe task")
    _add_standard_task_options(create_probe_parser)
    create_probe_parser.add_argument("--target-url", required=True, help="Target URL for the probe task")
    create_probe_parser.set_defaults(handler=_handle_create_probe_task)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the NAS CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    client = NasControlPlaneClient(args.base_url)
    payload = args.handler(client, args)
    if getattr(args, "command", None) == "task-report" and not getattr(args, "raw", False):
        print(_format_task_report(payload))
    else:
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


def _add_standard_task_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=True, help="Task id to create")
    parser.add_argument("--terminal-id", required=True, help="Terminal id to assign")
    parser.add_argument("--instance-id", help="BitBrowser instance id to target")
    parser.add_argument("--priority", type=int, default=0, help="Task priority")
    parser.add_argument("--retry-limit", type=int, default=0, help="Retry limit after the first attempt")
    parser.add_argument(
        "--annotate-remark",
        action="store_true",
        help="Append an annotate action after navigation",
    )


def _handle_create_follow_task(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.create_task(
        build_follow_task_payload(
            task_id=args.task_id,
            terminal_id=args.terminal_id,
            target_handle=args.target_handle,
            instance_id=args.instance_id,
            priority=args.priority,
            retry_limit=args.retry_limit,
            annotate_remark=bool(args.annotate_remark),
        )
    )


def _handle_create_chat_task(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.create_task(
        build_chat_task_payload(
            task_id=args.task_id,
            terminal_id=args.terminal_id,
            target_handle=args.target_handle,
            instance_id=args.instance_id,
            priority=args.priority,
            retry_limit=args.retry_limit,
            annotate_remark=bool(args.annotate_remark),
        )
    )


def _handle_create_probe_task(client: NasControlPlaneClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.create_task(
        build_probe_task_payload(
            task_id=args.task_id,
            terminal_id=args.terminal_id,
            target_url=args.target_url,
            instance_id=args.instance_id,
            priority=args.priority,
            retry_limit=args.retry_limit,
            annotate_remark=bool(args.annotate_remark),
        )
    )


def _format_task_report(report: dict[str, Any]) -> str:
    task = dict(report.get("task") or {})
    diagnostics = dict(report.get("diagnostics") or {})
    latest_log = dict(report.get("latest_log") or {})
    action_summary = dict(report.get("action_summary") or {})
    attempts = list(report.get("attempts") or [])

    lines = [
        f"task_id: {task.get('task_id')}",
        f"status: {task.get('status')}",
        f"script: {task.get('script_name')}",
        f"terminal: {task.get('terminal_id')}",
        f"health: {diagnostics.get('health_status')}",
        f"can_retry_now: {diagnostics.get('can_retry_now')}",
        f"attempts_total: {diagnostics.get('attempts_total')}",
        f"attempts_failed: {diagnostics.get('attempts_failed')}",
        f"attempts_completed: {diagnostics.get('attempts_completed')}",
        f"latest_error_code: {task.get('last_error_code')}",
        f"latest_error_message: {task.get('last_error_message')}",
        f"failure_category: {action_summary.get('failure_category')}",
        f"recommended_action: {action_summary.get('recommended_action')}",
        f"latest_log_level: {latest_log.get('level')}",
        f"latest_log_message: {latest_log.get('message')}",
    ]

    latest_failed_attempt = diagnostics.get("latest_failed_attempt")
    if isinstance(latest_failed_attempt, dict):
        lines.extend(
            [
                f"latest_failed_attempt_number: {latest_failed_attempt.get('attempt_number')}",
                f"latest_failed_attempt_status: {latest_failed_attempt.get('status')}",
                f"latest_failed_step: {latest_failed_attempt.get('failed_step_name')}",
                f"latest_failed_run_id: {latest_failed_attempt.get('run_id')}",
            ]
        )

    if attempts:
        lines.append("attempts:")
        for item in attempts:
            lines.append(
                "  "
                + f"#{item.get('attempt_number')} "
                + f"status={item.get('status')} "
                + f"category={item.get('failure_category')} "
                + f"failed_step={item.get('failed_step_name')} "
                + f"steps={item.get('step_count')}"
            )

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
