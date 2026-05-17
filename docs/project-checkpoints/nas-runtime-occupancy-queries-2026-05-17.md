# NAS Runtime Occupancy Queries Checkpoint

## 目标
- 让 NAS 查询接口和文本视图直接展示 terminal 当前运行态占用，而不是只能看到静态 task 列表。

## 阶段
- 当前阶段：运行态占用可观测性接入查询面

## 主线节点
- `active_task_count`
- `blocked_instance_ids`
- `wait_reason`
- `blocked_by_instance_id`

## 实现决策
- terminal registration / heartbeat 元数据新增 `blocked_instance_ids`。
- NAS terminal registry 持久化 `max_parallel_tasks`、`active_task_count`、`blocked_instance_ids`。
- NAS task claim 阶段会给暂未领取的任务写入等待原因：
  - `instance_blocked`
  - `slot_capacity_reached`
  - `retry_not_ready`
- 文本视图直接展示 terminal 占用信息和 task 等待原因，方便 CLI / demo 侧验证。

## 关键接口与数据流
- `terminal_agent.runtime.terminal_runtime.TerminalRuntime.registration_payload()`
- `terminal_agent.runtime.terminal_runtime.TerminalRuntime.heartbeat_payload()`
- `nas_control_plane.services.registry.TerminalRegistryService.record_heartbeat()`
- `nas_control_plane.services.tasks.TaskDispatchService.claim_tasks()`
- `nas_control_plane.views.render_terminal_summary()`
- `nas_control_plane.views.render_task_summary()`

## 已验证内容
- terminal 查询视图能看到：
  - `max_parallel_tasks`
  - `active_task_count`
  - `blocked_instance_ids`
- task 查询视图能看到：
  - `wait_reason`
  - `blocked_by_instance_id`
  - `retry_available_at`
- 当同实例任务被互斥挡住时，未领取任务会显示 `wait_reason=instance_blocked`。

## 验证
- `python -m nas_control_plane.demo_management_queries`
- `python -m terminal_agent.demo_instance_mutex_claim`
- `python -m compileall nas_control_plane terminal_agent shared`

## 未完成项与下一步
- 当前仍是文本视图优先，下一步应把这些字段接入：
  - NAS CLI 更细粒度过滤
  - dashboard / web console 的占用状态展示
  - terminal 当前占用实例与待执行队列的更明确拆分

## 关联链接
- `docs/system-purpose-and-requirements-baseline.md`
- `docs/project-checkpoints/terminal-instance-mutex-2026-05-17.md`
- `docs/project-checkpoints/terminal-active-slot-capacity-2026-05-17.md`
