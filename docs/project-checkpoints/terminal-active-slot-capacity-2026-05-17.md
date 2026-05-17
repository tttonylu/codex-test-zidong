# Terminal Active Slot Capacity Checkpoint

## 目标
- 让 terminal 的任务领取能力与当前执行占用联动，而不是只靠静态 `max_parallel_tasks`。

## 阶段
- 当前阶段：terminal 忙闲感知与领取容量联动

## 主线节点
- `active_task_count`
- `claim_capacity = max_parallel_tasks - active_task_count`
- `任务开始占槽 / 任务结束释放槽`

## 实现决策
- `TerminalState` 新增 `active_task_count`。
- runtime 在任务开始执行时增加占用，在结果回报后释放占用。
- `claim_capacity()` 改为动态计算剩余可领取容量。
- heartbeat 元数据增加 `active_task_count`，让 NAS 看到 terminal 当前执行占用。
- NAS terminal registry 在 heartbeat 中保留 `active_task_count`。

## 关键接口与数据流
- `terminal_agent.runtime.terminal_runtime.TerminalRuntime.mark_task_started()`
- `terminal_agent.runtime.terminal_runtime.TerminalRuntime.mark_task_finished()`
- `terminal_agent.runtime.terminal_runtime.TerminalRuntime.claim_capacity()`
- `terminal_agent.runtime.agent_loop.TerminalAgentLoop.run_cycle()`
- `nas_control_plane.services.registry.TerminalRegistryService.record_heartbeat()`

## 已验证内容
- 当 `max_parallel_tasks=1` 且 runtime 已存在 `active_task_count=1` 时，本轮 `claimed_tasks=0`，任务保持 `queued`。
- heartbeat 会把 `active_task_count=1` 和 `max_parallel_tasks=1` 一起上报到 NAS terminal metadata。
- 正常执行结束后，槽位会释放，后续 cycle 仍可继续领取剩余任务。

## 验证
- `python -m terminal_agent.demo_active_slot_capacity`
- `python -m terminal_agent.demo_slot_limited_execution`
- `python -m terminal_agent.demo_execution_loop`
- `python -m compileall nas_control_plane terminal_agent shared`

## 未完成项与下一步
- 当前只做了“任务数占槽”，还没做“实例占槽”。
- 下一步应继续补：
  - 同一 `instance_id` 的执行互斥
  - slot / instance 双重约束下的 claim 策略
  - terminal 侧活动槽位与任务列表的查询输出
  - 后续如接真并发执行，复用现有 `active_task_count` 语义

## 关联链接
- `docs/system-purpose-and-requirements-baseline.md`
- `docs/project-checkpoints/terminal-slot-limits-2026-05-17.md`
- `docs/project-checkpoints/automation-recovery-policy-2026-05-17.md`
