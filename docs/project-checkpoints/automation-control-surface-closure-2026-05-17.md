# Automation Control Surface Closure Checkpoint

## 目标
- 把这一阶段从“核心调度语义已成立”推进到“控制面已能直接观测和使用这些语义”。

## 阶段
- 当前阶段：控制面闭环

## 主线节点
- `runtime occupancy`
- `query filters`
- `cli usable`
- `dashboard reusable`

## 已完成范围
- 自动化主链已跑通并校正 lifecycle ordering。
- 失败语义、recovery policy、retry delay 已接入。
- terminal 领取约束已具备：
  - `max_parallel_tasks`
  - `active_task_count`
  - `instance mutex`
- NAS 查询面已具备：
  - terminal 运行态占用展示
  - task 等待原因展示
  - 细粒度过滤参数
- CLI 已支持直接查询这些运行态过滤结果。
- dashboard 已最小接入这些过滤条件和运行态字段。

## 关键接口与数据流
- `nas_control_plane.services.tasks.TaskDispatchService`
- `nas_control_plane.services.registry.TerminalRegistryService`
- `terminal_agent.runtime.TerminalRuntime`
- `terminal_agent.adapters.NasControlPlaneClient`
- `nas_control_plane.cli`
- `nas_control_plane.dashboard_html`

## 已验证内容
- `python -m compileall nas_control_plane terminal_agent shared`
- `python -m terminal_agent.demo_execution_loop`
- `python -m terminal_agent.demo_failure_paths`
- `python -m terminal_agent.demo_active_slot_capacity`
- `python -m terminal_agent.demo_instance_mutex_claim`
- `python -m nas_control_plane.demo_management_queries`
- `python -m nas_control_plane.demo_query_filters`
- `python -m nas_control_plane.demo_cli`
- `python -m nas_control_plane.demo_dashboard`

## 当前结论
- 这一轮已经不只是“后端能跑”，而是：
  - NAS 能查询为什么任务没被领取
  - CLI 能直接筛选这些状态
  - dashboard 能承接这些筛选和可观测字段
- 可以认为“核心自动化控制面第一阶段”基本成立。

## 下一步
- 如果继续主线，建议进入更高一层：
  - 真正的 terminal 并发 worker / slot 对象模型
  - 更真实的恢复调度策略
  - dashboard 进一步做成运营控制台而不是调试页

## 关联链接
- `docs/system-purpose-and-requirements-baseline.md`
- `docs/project-checkpoints/nas-query-filters-2026-05-17.md`
- `docs/project-checkpoints/nas-runtime-occupancy-queries-2026-05-17.md`
- `docs/project-checkpoints/terminal-instance-mutex-2026-05-17.md`
