# Terminal Concurrency And Recovery Phase Checkpoint

## 目标与范围
- 把 terminal 从“串行 claim 占位”推进到“真实并发 worker / slot 对象模型”。
- 把 terminal 重启后的未完成任务，从“本地丢失”推进到“NAS 可回收、可重排、可接管、可观测”。
- 把结果上报从“失败后仅内存保留”推进到“本地 durable outbox + 后续 cycle / 重启后 replay”。
- 把 `retry_pending` 拆成更可解释的 pending 家族，并补齐 `retry_kind` 观测。

## 当前阶段
- 当前主线阶段：terminal 并发执行、恢复调度、结果 durable replay 联动。

## 主线节点
- `concurrent slot workers`
- `slot persistence`
- `slot affinity`
- `terminal recovery requeue`
- `recovery terminal handoff`
- `result outbox replay`
- `pending state split`
- `retry kind observability`

## 相关分支与模块
- 当前落点：`main`
- terminal:
  - `terminal_agent/runtime/terminal_runtime.py`
  - `terminal_agent/runtime/agent_loop.py`
  - `terminal_agent/runtime/repositories.py`
  - `terminal_agent/runtime/store.py`
- NAS:
  - `nas_control_plane/services/tasks.py`
  - `nas_control_plane/services/recovery.py`
  - `nas_control_plane/services/registry.py`
  - `nas_control_plane/services/audit.py`
  - `nas_control_plane/server.py`
  - `nas_control_plane/views.py`
  - `nas_control_plane/cli.py`
  - `nas_control_plane/dashboard_html.py`

## 关键接口与数据流
- terminal runtime 维护本地 `slots` 持久化视图，并在 registration / heartbeat 中上报：
  - `slot_count`
  - `slots`
  - `recovered_task_ids`
  - `result_outbox_count`
- terminal agent loop 按 slot 容量并发提交 worker 执行。
- worker 完成后：
  - 结果提交成功：直接 release slot
  - 结果提交失败：写入本地 `result_outbox`，再 release slot
- 后续 cycle 启动时，loop 先 replay 本地 result outbox；成功项才从 outbox ack 删除。
- terminal 重启时，本地 unfinished slot 会被恢复为 `recovered_task_ids_pending`，并随 heartbeat 上报给 NAS。
- NAS `/heartbeat` 对每个 recovered task 单独处理：
  - 成功 requeue: 进入 `accepted_recovered_task_ids`
  - NAS 不存在该任务: 进入 `missing_recovered_task_ids`
- terminal 仅 ack `accepted_recovered_task_ids`，不会因为 heartbeat `200 OK` 就清空全部 pending recovery ids。

## 实现决策
- 并发不再只靠 `active_task_count` 数字占位，而是引入真实 `ScriptSlot` 对象池。
- slot 状态本地持久化；terminal 重启后恢复 unfinished slot，并把对应 task 交给 NAS 回收。
- 结果 durable replay 不单独起新服务，先复用 terminal 本地 state 文件中的 `result_outbox` section。
- outbox replay 保持最小语义：
  - 只在 `submit_task_result()` 成功后 ack 删除
  - 失败项继续保留，留待下一 cycle / 重启后继续 replay
- slot 选择保留轻量亲和策略：
  - 优先复用最近跑过相同 `instance_id` 的 slot
  - 其次复用最近跑过相同 `script_name` 的 slot
  - 否则选择最少使用 slot
- pending 状态从单一 `retry_pending` 拆分为：
  - `manual_retry_pending`
  - `terminal_recovery_pending`
  - `retry_pending` 仅保留为历史兼容别名

## 已验证内容
- terminal 可按 slot 真并发执行 worker。
- slot 状态可持久化，terminal 重启后可恢复 unfinished task id 并上报 NAS。
- 结果提交失败后会写入本地 durable outbox，而不是只靠内存中的 future/slot 保留。
- terminal 重启后可先 replay outbox，再继续主执行循环。
- NAS 可将 recovery task 重排到 pending，并在后续 claim 中优先于普通 queued task。
- recovery ack 现在是逐项确认，而不是整批乐观清空。
- terminal slot metadata 与 `result_outbox_count` 已能在 runtime metadata 中直接观测。

## 验证
- `python -m compileall nas_control_plane terminal_agent docs`
- `python -m terminal_agent.demo_concurrent_slots`
- `python -m terminal_agent.demo_slot_affinity_selection`
- `python -m terminal_agent.demo_slot_recovery_persistence`
- `python -m terminal_agent.demo_slot_recovery_reset`
- `python -m terminal_agent.demo_result_submit_failure_retains_slot`
- `python -m nas_control_plane.demo_recovery_priority_claim`
- `python -m nas_control_plane.demo_terminal_recovery_requeue`
- `python -m nas_control_plane.demo_recovery_terminal_handoff`
- `python -m nas_control_plane.demo_recovery_ack_partial_acceptance`
- `python -m terminal_agent.demo_recovery_ack_only_accepted_ids`
- `python -m nas_control_plane.demo_terminal_slot_observability`

## 结论
- terminal 真并发 worker / slot 对象模型已在主线落地。
- terminal recovery 已进入 NAS 调度语义，而不是停留在 terminal 本地自愈。
- durable result outbox 第一版已落地，主线不再把结果提交失败理解为“只能等当前进程活着时重试”。

## 未完成项与下一步
- 仍缺一次用户侧人工控制面验收，重点看 dashboard 运营可用性。
- 当前 durable outbox 只覆盖 result submit replay；还未覆盖未来 queue transport 的 claim/ack/lease 持久化。
- 最终 NAS 部署目标仍是 fnOS 图形化 Docker；容器/项目命名需继续保持强隔离标识，避免与其他容器混淆。
- 下一阶段可继续推进：
  - real queue transport
  - queue claim/ack/lease persistence
  - 更完整的跨 terminal recovery / affinity / handoff 策略

## 关联链接
- `docs/system-purpose-and-requirements-baseline.md`
- `docs/project-checkpoints/automation-control-surface-closure-2026-05-17.md`
- `docs/project-checkpoints/queue-mode-skeleton-boundary-2026-05-18.md`
- `docs/project-checkpoints/mainline-review-brief-terminal-concurrency-and-queue-skeleton-2026-05-18.md`
