# Automation Failure Paths Checkpoint

## 目标
- 把自动化主链的失败语义也跑通，不只验证成功路径。

## 覆盖路径
- `bitbrowser.open_failed`
- `bitbrowser.close_failed`
- `worker.missing_instance_id`
- `worker.unsupported_script`

## 实现决策
- worker 错误分类从粗粒度拆成更明确的错误码。
- NAS 任务状态区分 `retryable_failure` 和 `terminal_failure`。
- retry demo 改成独立 state 文件，确保中间状态可重复验证。

## 验证
- `python -m nas_control_plane.demo_task_retry_limit`
- `python -m terminal_agent.demo_failure_paths`
- `python -m compileall nas_control_plane terminal_agent shared`

## 当前结论
- 第一次可恢复失败会进入 `retryable_failure`，`retryable=true`，`final=false`。
- 超过 retry 上限后会进入 `terminal_failure`，并记录 `retry_blocked_reason=retry_limit_exceeded`。
- 非可恢复错误如 `missing_instance_id / unsupported_script / close_failed` 会直接进入终态失败。

## 后续建议
- 下一步做恢复策略和调度策略，例如任务回退、延迟重试、按错误码分流。
