# Terminal Instance Mutex Checkpoint

## 目标
- 避免 terminal 在同一轮领取或执行多个绑定同一 `instance_id` 的任务。

## 阶段
- 当前阶段：任务槽位约束升级为“任务槽位 + 实例互斥”双约束

## 主线节点
- `blocked_instance_ids`
- `同一 claim 批次实例去重`
- `运行中实例占用不再重复领取`

## 实现决策
- terminal claim 请求新增 `blocked_instance_ids`，上报当前运行中任务占用的实例集合。
- NAS `TaskDispatchService.claim_tasks()` 增加实例互斥过滤：
  - 已在 terminal 运行中的实例不再返回
  - 同一批 claim 中，同一个 `instance_id` 只返回一个任务
- claim 限额逻辑改为“排序后逐个挑选直到满足 limit”，而不是先截断再去重，避免高优先级重复实例把可用实例任务挤掉。
- demo 改用动态端口，减少本地固定端口残留干扰。

## 关键接口与数据流
- `terminal_agent.runtime.terminal_runtime.TerminalRuntime.blocked_instance_ids()`
- `terminal_agent.adapters.nas_client.NasControlPlaneClient.claim_tasks()`
- `nas_control_plane.server /tasks/claim`
- `nas_control_plane.services.tasks.TaskDispatchService.claim_tasks()`

## 已验证内容
- 当 `max_parallel_tasks=2` 且 3 个任务中有 2 个绑定同一 `instance_id` 时：
  - 第 1 轮只领取其中一个同实例任务，加上另一个不同实例任务
  - 剩余同实例任务保持 `queued`
  - 第 2 轮才再次领取该剩余任务
- `attempt_count` 仍保持每任务 1 次，没有重复执行。
- 现有 active-slot 与 slot-limit demo 均保持通过。

## 验证
- `python -m terminal_agent.demo_instance_mutex_claim`
- `python -m terminal_agent.demo_active_slot_capacity`
- `python -m terminal_agent.demo_slot_limited_execution`
- `python -m compileall nas_control_plane terminal_agent shared`

## 未完成项与下一步
- 现在仍是串行执行模型，实例互斥已经有语义，但还没有真正的并发 worker 槽位对象。
- 下一步应继续补：
  - 显式 slot / instance 占用视图
  - 多 terminal 下的实例分配和冲突策略
  - 失败中断后实例释放/恢复策略
  - NAS 查询接口展示 terminal 当前占用实例

## 关联链接
- `docs/system-purpose-and-requirements-baseline.md`
- `docs/project-checkpoints/terminal-active-slot-capacity-2026-05-17.md`
- `docs/project-checkpoints/terminal-slot-limits-2026-05-17.md`
