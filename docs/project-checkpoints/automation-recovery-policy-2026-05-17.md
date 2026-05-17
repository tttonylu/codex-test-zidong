# Automation Recovery Policy Checkpoint

## 目标
- 把失败恢复从“只有错误码”推进到“错误码驱动的处理策略”。

## 阶段
- 当前阶段：恢复语义与重试调度约束

## 主线节点
- `error_code -> recovery policy`
- `recovery policy -> retryable/final`
- `retryable_failure -> retry_pending -> 可领取时间窗口`

## 实现决策
- NAS 新增统一恢复策略映射，按 `error_code` 给出：
  - `retryable`
  - `failure_category`
  - `recommended_action`
  - `retry_delay_seconds`
- `record_result()` 不再只记录失败字符串，而是把恢复建议和失败分类落入 task 参数。
- `retry_task()` 为 `retry_pending` 写入 `retry_available_at`，避免任务进入重试后立刻再次被 claim。
- `claim_tasks()` 对 `retry_pending` 增加时间窗口判断，只有到达 `retry_available_at` 后才允许重新派发。
- 当 worker 显式传入 `retryable=true/false` 时，优先尊重 worker 结果；只有未显式提供时才回退到错误码策略。

## 关键接口与数据流
- `nas_control_plane.services.recovery.resolve_recovery_policy(error_code)`
- `nas_control_plane.services.tasks.TaskDispatchService.record_result()`
- `nas_control_plane.services.tasks.TaskDispatchService.retry_task()`
- `nas_control_plane.services.tasks.TaskDispatchService.claim_tasks()`

## 已验证内容
- `bitbrowser.open_failed` 会进入 `retryable_failure`，并生成延迟重试建议。
- `bitbrowser.close_failed` 会直接进入 `terminal_failure`，建议人工检查窗口状态。
- `worker.unsupported_script` 会直接进入 `terminal_failure`，建议修正任务定义。
- `retry_pending` 任务在 `retry_available_at` 之前不会被重新 claim，到达时间后才重新进入派发。

## 验证
- `python -m nas_control_plane.demo_recovery_policy`
- `python -m nas_control_plane.demo_retry_scheduling`
- `python -m nas_control_plane.demo_task_retry_limit`
- `python -m compileall nas_control_plane terminal_agent shared`

## 未完成项与下一步
- 现在只有“可领取时间”这一层，下一步应继续补：
  - terminal 侧执行槽位/并发控制
  - 多任务 claim 后的执行顺序策略
  - 更明确的 stop/continue 策略
  - 恢复策略与 NAS 查询视图联动

## 关联链接
- `docs/system-purpose-and-requirements-baseline.md`
- `docs/project-checkpoints/automation-lifecycle-2026-05-17.md`
- `docs/project-checkpoints/automation-failure-paths-2026-05-17.md`
