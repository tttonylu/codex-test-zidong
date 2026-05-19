# 项目需求完整梳理

> 基于 2026-05-19 用户对话汇总

## 一、最终产品目标

矩阵化自动关注 / 自动聊天总控系统。

以 NAS 为唯一总控入口，多终端为执行节点，BitBrowser 实例为账号运行位，Chrome 插件脚本为主执行器，实现多台电脑、多组 BitBrowser 实例、多个账号长期稳定自动执行关注、破冰、聊天、广告。

主链路：`NAS → 终端 → 实例(BitBrowser) → 插件脚本 → 页面动作执行 → 结果/统计回传 NAS`

---

## 二、已实现的核心能力

### 2.1 架构分层
| 层 | 职责 |
|---|---|
| NAS 总控 (`nas_control_plane/`) | 任务调度、终端注册、实例总览、策略分发、统计审计 |
| 终端代理 (`terminal_agent/`) | 本机 BitBrowser 扫描、任务承接、脚本生命周期控制、状态上报 |
| 实例 (BitBrowser 窗口) | 账号运行位，持有登录状态，承载插件执行 |
| 脚本 (Chrome 扩展 X-Matrix-Bot) | 执行 follow/chat/probe/extract 页面动作 |

### 2.2 任务生命周期
`queued → dispatched → running → completed / retryable_failure / terminal_failure / cancelled`

### 2.3 恢复链路（已有）
- 终端重启 → slot 持久化 → NAS heartbeat ACK → recovery requeue → 重新分配执行
- 结果提交失败 → 本地 outbox → 后续 cycle / 重启后 replay
- 失败路径覆盖 6 种错误码（bitbrowser.request_failed / open_failed / close_failed 等）

### 2.4 弹药库 / 活动（已有）
- `/plugin/ammo/add` 添加博主 ID 到弹药库
- `claim_plugin_ammo_target` / `consume_plugin_ammo_target` 领取消耗
- `upsert_plugin_campaign` 活动管理 + 文案

### 2.5 每日统计（已有）
- `DailyActionStatRecord` 按账号按天存储关注/私信/广告/拉黑等动作统计
- `retention_days=15` 保留 15 天自动清理

### 2.6 部署
- NAS Docker: `deploy/nas-control-plane/docker-compose.yml`
- fnOS 目标: 192.168.0.100:3210，容器名 `codex-matrix-bplus-nas-control`
- 终端: Windows 运行 `python -m terminal_agent.run_plugin_bridge`

---

## 三、本次新增：终端实例健康巡检与自动重启（2026-05-19）

### 核心目的
自动化无人看守运行的核心——当脚本长时间运行卡死、浏览器内存爆掉、页面白屏无响应、网络被限制时，自动重启实例并恢复任务。

### 检测项
| 检测 | 方式 | 默认阈值 |
|---|---|---|
| 脚本超时 | slot start 时间持续超过 N 秒 | 600 秒（10 分钟） |
| 内存超标 | 通过 BitBrowser `/browser/pids` 查 PID → 系统 tasklist 查 WorkingSet | 800 MB |
| DOM 卡死 | 插件扩展上报 DOM 是否健康，连续 N 次失联即判定卡死 | 3 次 |

### 保护机制
| 机制 | 参数 |
|---|---|
| 冷却期 | 同一实例 N 个 cycle 内不重复重启（默认 6 次） |
| 上限封顶 | 单实例自动重启 M 次后停止（默认 3 次），转为告警等待人工 |
| 任务恢复 | 重启前释放 slot 标记 failed → 已有 NAS recovery 链路自动接管 |

### 触发链路（每轮 run_cycle）
```
scan → heartbeat → sync
  → health_monitor.check_all(slots, pid_map)
  → register_health_action() → 标记 restart_requested
  → _execute_pending_restarts()
    → fail 该实例上运行的 slot
    → close_browser → sleep(5s) → open_browser
    → NAS 同步 → request_instance_restart
  → claim 新任务（跳过 restarting 中的实例）
```

### 插件对接（新增 `/ext/dom_health`）
Chrome 扩展 content script 定期 POST `http://127.0.0.1:54346/ext/dom_health`
```json
{"instance_id": "browser-xxx", "alive": true}
```
现有 `content_follow.js` / `content_chat.js` 已有 Watchdog 检测 DOM，只需加一行 fetch 上报即可升级为实例重启（不再只是刷新页面）。

### 已验证
8 项单元测试全部通过：脚本超时、健康无动作、DOM 失联、DOM 重置、内存查询容错、冷却期、上限封顶、TerminalRuntime 集成。

---

## 四、待建设：运营控制面（NAS Dashboard 增强）

### 4.1 实例管理面板（终端→实例→操作）
用户操作流程：
```
打开 NAS 网页 → 先看终端列表（选择哪台电脑）
  → 点击一个终端 → 看该终端下的实例列表（已备注好的账号，如 @user1 / @user2）
    → 复选框选择（全选 / 逐个点选）
    → 四个操作按钮：
```
| 按钮 | 功能 |
|---|---|
| **全自动启动** | 为该账号同时开两个 BitBrowser 页面，一个跑 content_follow.js，一个跑 content_chat.js，分别独立执行 |
| **停止** | 停止该账号上的脚本运行（通过 engine 命令通道） |
| **关闭** | 关闭该 BitBrowser 窗口 |
| **打开** | 打开该 BitBrowser 窗口 |

**要求**：
- 实例以卡片展示，显示：备注名 / handle / 运行状态 / 健康状态
- 复选框 + 全选按钮（页头）
- 选中后批量操作（全自动启动可单选不支持批量）
- 两个脚本必须两个独立页面分别运行，不能多开页面

### 4.2 弹药库
已有能力：添加博主 ID、领取、消耗
需确认是否满足"存储、接收、发放"三个需求，可能需要优化展示面。

### 4.3 日报表（保留 15 天）
后端已有 `daily_action_stats` 数据，需在 Dashboard 展示：
- 按账号查看
- 每日数据：关注量 / 破冰数 / 广告数 / 拉黑数
- 保留 15 天，自动清理过期数据

### 4.4 黑名单
- **来源**：聊天脚本检测到被目标拉黑 → 上传该目标 ID 到 NAS
- **存储**：NAS 侧维护全局黑名单列表
- **消费**：所有账号自动跳过黑名单中的 ID，不发送消息
- **管理**：Dashboard 可查看 / 手动添加 / 删除黑名单

---

## 五、开发原则

1. **NAS 是唯一总入口** — 不能把插件自主抢任务当成主入口
2. **插件是主执行器** — 终端和实例只是承载与调度层
3. **任务语义必须业务化** — 做"账号 + 目标 + 动作串"
4. **主视图必须运营可读** — 先让人看懂哪些账号在线、哪个实例在跑、今天跑了多少
5. **实例稳定性是高优先级** — 长时间运行导致卡顿、占内存、假死是主业务风险，必须支持状态观测、异常标记、重启恢复
6. **先理解指令再执行** — 不急于动手改动，有疑问先问清楚
7. **所有操作只针对工作区源文件** — 不改 .deploy-temp/ .tmp_nas_deploy_bundle/ 下的副本
