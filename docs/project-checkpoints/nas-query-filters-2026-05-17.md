# NAS Query Filters Checkpoint

## 目标
- 给 NAS 查询接口补充可直接复用的细粒度过滤，而不是把筛选逻辑留到 CLI 或页面层。

## 阶段
- 当前阶段：运行态与等待态的后端过滤能力

## 主线节点
- `terminals query filters`
- `tasks query filters`
- `wait_reason filters`
- `blocked_by_instance_id filters`

## 实现决策
- terminal 查询新增过滤：
  - `min_active_task_count`
  - `max_parallel_tasks`
  - `blocked_instance_id`
- task 查询新增过滤：
  - `wait_reason`
  - `blocked_by_instance_id`
- server / client / CLI 全链路一起接入这些参数，避免只在某一层可用。
- 新增 `demo_query_filters.py` 作为最小验证脚本。

## 关键接口与数据流
- `nas_control_plane.services.registry.TerminalRegistryService.list_terminals()`
- `nas_control_plane.services.tasks.TaskDispatchService.query_tasks()`
- `nas_control_plane.server /terminals`
- `nas_control_plane.server /tasks`
- `terminal_agent.adapters.nas_client.NasControlPlaneClient.list_terminals()`
- `terminal_agent.adapters.nas_client.NasControlPlaneClient.query_tasks()`
- `nas_control_plane.cli`

## 已验证内容
- 可按 `wait_reason=slot_capacity_reached` 查询到未领取任务。
- 可按 `max_parallel_tasks=1` 查询到对应 terminal。
- 管理查询 demo 仍能正确展示 terminal 占用和 task 等待原因。
- 实例互斥 demo 仍保持通过。

## 验证
- `python -m nas_control_plane.demo_query_filters`
- `python -m nas_control_plane.demo_management_queries`
- `python -m terminal_agent.demo_instance_mutex_claim`
- `python -m compileall nas_control_plane terminal_agent shared`

## 未完成项与下一步
- 当前过滤只覆盖了一部分运行态，下一步应继续补：
  - `retry_not_ready` 的更细查询
  - terminal 当前 blocked instance 的更细列表查询
  - dashboard / web console 直接复用这些过滤能力

## 关联链接
- `docs/project-checkpoints/nas-runtime-occupancy-queries-2026-05-17.md`
- `docs/project-checkpoints/terminal-instance-mutex-2026-05-17.md`
- `docs/system-purpose-and-requirements-baseline.md`
