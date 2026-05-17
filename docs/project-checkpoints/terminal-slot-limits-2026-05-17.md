# Terminal Slot Limits Checkpoint

## 目标
- 给 terminal 增加基础执行槽位约束，避免一轮 claim 全部任务。

## 阶段
- 当前阶段：terminal 侧吞吐控制基线

## 主线节点
- `terminal max_parallel_tasks`
- `claim limit -> NAS task claim`
- `多任务分批执行`

## 实现决策
- terminal runtime 新增 `max_parallel_tasks` 配置。
- terminal 在注册和 heartbeat 元数据中上报 `max_parallel_tasks`。
- NAS `/tasks/claim` 接口支持 `max_tasks` 限额参数。
- `TaskDispatchService.claim_tasks()` 在优先级排序后只返回本轮允许领取的任务数。
- agent loop 每轮按 terminal 可用槽位向 NAS 领取任务，而不是无上限拉取。

## 关键接口与数据流
- `terminal_agent.runtime.terminal_runtime.TerminalRuntime.claim_capacity()`
- `terminal_agent.adapters.nas_client.NasControlPlaneClient.claim_tasks()`
- `nas_control_plane.server /tasks/claim`
- `nas_control_plane.services.tasks.TaskDispatchService.claim_tasks()`

## 已验证内容
- 当 `max_parallel_tasks=1` 且存在 3 个可执行任务时，terminal 会分 3 个 cycle 各执行 1 个任务。
- 每个任务只执行 1 次，`attempt_count=1`，没有重复 claim。
- 原成功主链 demo 仍保持通过，未被 claim 限额改动破坏。

## 验证
- `python -m terminal_agent.demo_slot_limited_execution`
- `python -m terminal_agent.demo_execution_loop`
- `python -m terminal_agent.demo_task_lifecycle`
- `python -m compileall nas_control_plane terminal_agent shared`

## 未完成项与下一步
- 当前只有“每轮领取上限”，还没有真正的并发 worker 槽位模型。
- 下一步应继续补：
  - 领取数量与本地忙闲槽位联动
  - 不同实例之间的执行占用约束
  - 多任务顺序策略和抢占/暂停语义
  - terminal 运行时视图中的槽位状态查询

## 关联链接
- `docs/system-purpose-and-requirements-baseline.md`
- `docs/project-checkpoints/automation-recovery-policy-2026-05-17.md`
- `docs/project-checkpoints/automation-lifecycle-2026-05-17.md`
