# NAS Control Plane Deployment And Queue Next Phase

## 目标与范围
- 把当前 NAS 总控从“本地开发可运行”推进到“可按 fnOS Docker 形态落地”的部署骨架。
- 为下一阶段 queue 化分发预留清晰边界，但不把 NAS 重新做成重执行节点。

## 当前部署结论
- 已提供第一版 NAS Docker 部署骨架：
  - `nas_control_plane/Dockerfile`
  - `deploy/nas-control-plane/docker-compose.yml`
  - `deploy/nas-control-plane/.env.example`
  - `deploy/nas-control-plane/README.md`
- 当前命名隔离策略已明确：
  - compose project: `codex_matrix_bplus_nas`
  - container: `codex-matrix-bplus-nas-control`
  - deployment marker: `codex-matrix-bplus`
- 这一命名策略保留，作为后续 fnOS 图形化 Docker 部署时的专用特殊标识。

## 已验证内容
- `python -m compileall nas_control_plane terminal_agent docs`
- `python deploy/nas-control-plane/verify_deployment.py`
- `verify_deployment.py` 现已改为使用动态空闲端口，避免固定端口命中旧进程导致假阳性/假阴性。

## 当前说明
- `verify_deployment.py` 当前仍是轻量 smoke，但已覆盖到当前 queue skeleton 的最新观测面：
  - 服务可启动
  - dashboard 可访问
  - task create 后 state 文件可落盘
  - `queue_pull` task create 可返回 `queue_dispatch_status` / `queue_dispatch_accepted`
  - HTTP query 可按 queue dispatch outcome 过滤
  - dashboard HTML 已包含 queue dispatch filter 控件
- 上线前仍需真实容器内写路径与卷挂载验证。

## 从旧项目提炼的约束
- NAS 侧保持轻量：
  - API
  - state
  - dashboard
  - audit
- 重浏览器执行与高内存任务继续留在 terminal / workstation。
- fnOS 图形化 Docker 部署时必须保持容器命名与项目命名的显式隔离。
- compose 配置变更时，应走 recreate，而不是只做 restart。

## 下一阶段：队列化分发候选
- 当前主线继续使用 `claim_http` 闭环。
- 下一阶段可以引入 Redis / queue，但边界必须保持：
  - NAS:
    - 任务入队
    - recovery / affinity / priority 决策
    - audit / state snapshot
  - terminal:
    - 消费指令
    - 本地 slot 执行
    - 本地恢复 / outbox / 状态缓存
- 不在下一阶段做的事：
  - 把 NAS 变成重执行 worker
  - 把 dashboard 变成调度核心
  - 提前引入复杂分布式组件但没有清晰接口边界

## 接口预留建议
- NAS side reserve:
  - `dispatch_mode = claim_http | queue_pull`
  - `queue_topic` / `terminal_channel`
  - `delivery_id` / `claim_lease_id`
- terminal side reserve:
  - local outbox for result replay
  - queue consumer ack/retry hooks
  - recovery handoff audit markers

## 关联链接
- `deploy/nas-control-plane/README.md`
- `docs/project-checkpoints/terminal-concurrency-and-recovery-phase-2026-05-18.md`
- `docs/project-checkpoints/queue-mode-skeleton-boundary-2026-05-18.md`
- `docs/system-purpose-and-requirements-baseline.md`
