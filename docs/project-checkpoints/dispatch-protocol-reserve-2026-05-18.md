# Dispatch Protocol Reserve Checkpoint

## 目标
- 在不引入真实 Redis / queue transport 的前提下，为下一阶段保留最小协议字段。

## 当前策略
- 当前主线仍使用 `claim_http`。
- 新增字段只作为透传与观测预留，不改变当前调度行为。

## 已预留字段
- `TaskAssignmentPayload`
  - `dispatch_mode`
  - `queue_topic`
  - `delivery_id`
  - `claim_lease_id`
- `ActionResultPayload`
  - `delivery_id`
  - `claim_lease_id`

## 数据流
- NAS 创建 task 时，把这些字段落入 task parameters。
- terminal claim 后，把 `delivery_id` / `claim_lease_id` 带到执行元数据。
- 结果回执再把这两个字段带回 NAS，用于未来接入：
  - queue ack
  - lease timeout
  - replay / dedupe

## 当前结论
- 当前主线没有被 Redis 绑定。
- 但如果下一阶段引入队列化分发，协议层不需要再从零补字段。

## 关联链接
- `docs/project-checkpoints/queue-mode-skeleton-boundary-2026-05-18.md`
- `docs/project-checkpoints/nas-control-plane-deployment-and-queue-next-phase-2026-05-18.md`
