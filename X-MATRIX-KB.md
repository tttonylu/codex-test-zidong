# X-Matrix Bot 项目知识库

> 最后更新：2026-05-08
> 项目路径：`C:\Users\陆先生\.cursor\自动化\opencode`

---

## 1. 项目概述

- **项目名称**：X-Matrix Bot
- **核心功能**：Twitter/X 自动化管理 + BitBrowser 窗口控制 + NAS 数据管理
- **技术栈**：Flask (NAS后端) + Chrome Extension MV3 + Python GuardAgent + FastAPI (GuardAgent HTTP) + PostgreSQL

---

## 2. 核心组件架构

### 2.1 NAS 后端 (x_matrix_nas/)

- **server.py** - Flask 主服务，提供 REST API
- **database.py** - 数据库抽象层（PostgreSQL/SQLite 双模式）
- **核心表**：
  - `profile_state` (实例状态表) - 包含 profile_id, handle, window_id, status, archived
  - `daily_stats_*` (每日统计)
  - `operation_log` (操作日志)
- **关键接口**：
  - `/api/user-id-report` (扩展上报)
  - `/api/profiles` (获取活跃实例)
  - `/api/pending-actions` (GuardAgent 拉取指令)
  - `/api/action-result` (GuardAgent 上报结果)
  - `/api/sync-windows` (GuardAgent 兜底同步)
  - `/api/dashboard_data` (Dashboard 数据)

### 2.2 Chrome 扩展 (X-Matrix-Bot/)

- **manifest.json** - MV3 扩展配置
- **background.js** - Service Worker，处理消息转发和心跳
- **content_id_extractor.js** - 提取 handle 和 window_id，上报 NAS
- **content_chat.js** - 私信引擎
- **content_follow.js** - 关注引擎
- **options.html/js** - 诊断工具
- **上报链路**：content script → background.js → NAS `/api/user-id-report`

### 2.3 GuardAgent (scrm_monitor/windows_agent/)

- **guard_agent.py** - 守护进程，轮询 NAS 执行 BitBrowser API 调用
- **config.py** - 配置（NAS_BASE_URL, BITBROWSER_API_URL）
- **核心方法**：
  - `get_pending_actions()` - 从 NAS 拉取指令
  - `find_window_id()` - 匹配 profile_id → BitBrowser window_id
  - `open_window()` - 启动窗口（带 `#bit_id=` URL hash）
  - `stop_window()` - 关闭窗口
  - `restart_window()` - 重启窗口
  - `sync_windows()` - 兜底同步窗口列表到 NAS
- **BitBrowser Local API**: `http://127.0.0.1:54345`

### 2.3.1 V11.9.0 终端统一上报架构

**核心原则**：GuardAgent 是 Windows 终端上的**唯一数据汇聚点**，Chrome 扩展只向 GuardAgent 上报，GuardAgent 汇总后统一上报 NAS。

```
总控(NAS Dashboard) ← 终端(GuardAgent:54346) ← 子实例(BitBrowser窗口) ← 脚本(Chrome扩展)
```

**数据流**：
1. Chrome 扩展从 X.com 提取 handle → 上报 GuardAgent (`/ext/user_id`)
2. GuardAgent 收到 handle + bit_id → 查找对应 BitBrowser 窗口
3. GuardAgent 自动调用 BitBrowser API 设置 `remark = handle`
4. GuardAgent 汇总所有数据 → 批量同步到 NAS (`/api/guard/sync`)
5. Dashboard 显示：一个 handle 一个卡片，无重复

**GuardAgent HTTP 服务**：
- 端口：`127.0.0.1:54346`
- 框架：FastAPI + uvicorn
- 端点：
  - `POST /ext/heartbeat` - 接收扩展心跳
  - `POST /ext/user_id` - 接收 handle 上报
  - `POST /ext/action_log` - 接收扩展战报
  - `GET /healthz` - 健康检查

**三层心跳**：
```
扩展 ──(5s)──► GuardAgent ──(15-30s)──► NAS ──(60s)──► Dashboard
```

**profile_id 格式**：`@handle#guard`（固定格式，不再使用随机 instanceId）

### 2.4 Dashboard 路由与模板（重要！）

| 路由 | 模板 | 用途 | 内容 |
|------|------|------|------|
| `/` | `index.html` | **主页** | 情报决策大屏，包含探针、弹药库、其他容器链接 |
| `/dashboard` | `home.html` | **运营大屏** | 实例卡片、restart/stop/open 按钮、统计数据 |

**⚠️ 注意**：
- `/` 是主页（链接到其他容器），**不显示实例卡片**
- `/dashboard` 是运营大屏，**显示实例卡片**
- 两个模板文件都在 `x_matrix_nas/templates/` 目录下
- 修改路由后必须重启 NAS 容器才能生效

---

## 3. 当前已知问题（截至 2026-05-08 V11.9.0）

### 3.1 已解决

1. ✅ **Dashboard 重复卡片** - V11.9.0 终端统一上报架构，一个 handle 一个卡片
2. ✅ **GuardAgent 疯狂重启** - 移除了 auto_monitor_loop 自动重启逻辑
3. ✅ **扩展 window_id 上报不可靠** - 改为 GuardAgent 主动扫描 BitBrowser remark
4. ✅ **随机 instanceId 导致重复** - 统一使用 `@handle#guard` 固定格式
5. ✅ **扩展直连 NAS 导致数据分散** - 扩展改为上报 GuardAgent，GuardAgent 统一同步 NAS

### 3.2 当前注意事项

1. **数据库使用 PostgreSQL** - 容器环境变量 `DB_TYPE=postgresql`，不是 SQLite
2. **扩展需要重新加载** - 修改扩展代码后必须在 chrome://extensions 重新加载
3. **GuardAgent 需要重启** - 修改 guard_agent.py 后需要重启进程
4. **BitBrowser remark 自动设置** - GuardAgent 根据扩展上报的 handle 自动设置窗口 remark
5. **PostgreSQL 大小写敏感** - `DISTINCT ON (handle)` 区分大小写，必须用 `LOWER(handle)` 去重
6. **NAS 容器代码同步** - 修改 `opencode/` 下的文件后，必须 SCP 上传到 NAS 并重启容器
7. **Dashboard 路由** - `/` = 主页（index.html），`/dashboard` = 运营大屏（home.html），不要搞反

---

## 4. 核心需求

### 4.1 必须满足

1. Dashboard 上每个 Twitter 账号只显示一个卡片
2. 点击 restart/stop/open 按钮能正确控制对应的 BitBrowser 窗口
3. GuardAgent 不要疯狂重启
4. 更换 Twitter 账号时，旧数据自动归档，新数据独立

### 4.2 期望满足

5. 扩展能稳定上报 window_id
6. 诊断工具能正确显示窗口映射状态
7. 离线检测合理（不误判）

---

## 5. 推倒重来方案

### 5.1 步骤 1：完全清理

- 停止 GuardAgent
- 停止 NAS 容器
- 清空 `profile_state` 表（或重建）
- 清空 `pending_actions`
- 删除所有测试数据

### 5.2 步骤 2：简化设计

- 禁用 `auto_monitor_loop()` 的自动重启（改为手动触发）
- Dashboard 按 handle 去重显示（不显示多个 instanceId）
- GuardAgent 只处理明确的 pending_actions，不主动扫描

### 5.3 步骤 3：重新验证

- 启动干净的 NAS
- 打开一个 BitBrowser 窗口，登录 Twitter
- 扩展上报 window_id
- Dashboard 显示一个卡片
- 点击按钮测试控制

### 5.4 步骤 4：逐步扩展

- 测试更换账号流程
- 测试多窗口场景
- 重新启用自动检测（可选）

---

## 6. 关键文件路径

| 组件 | 路径 |
|------|------|
| 扩展源文件 | `C:\Users\陆先生\.cursor\自动化\opencode\X-Matrix-Bot\` |
| NAS 源文件 | `C:\Users\陆先生\.cursor\自动化\opencode\x_matrix_nas\` |
| GuardAgent | `C:\Users\陆先生\.cursor\自动化\opencode\scrm_monitor\windows_agent\` |
| BitBrowser 扩展目录 | `~\AppData\Roaming\BitBrowser\BitExtensions\64562e88-c64a-4d31-8378-ee9ad6054a30` |
| NAS Docker | `/vol2/1000/Awork/x-matrix-test/x_matrix_nas/` |

---

## 7. 调试方法

1. 运行 `test_nas_api.py` 测试 NAS API
2. 运行 `cleanup_old_profiles.py` 分析重复数据
3. 查看 GuardAgent 日志（`guard_agent.log`）
4. 查看 NAS 容器日志（`docker logs`）
5. 扩展提示框显示实时上报状态（替代 `console.log`）

---

## 8. 修改记录模板

每次修改必须记录：

- [ ] 修改时间
- [ ] 修改文件
- [ ] 修改原因
- [ ] 修改内容摘要
- [ ] 验证结果
- [ ] 是否更新版本号

### 修改记录 2026-05-07（推倒重来 - 清理与禁用 sync）

- **修改时间**：2026-05-07
- **修改文件**：
  - `scrm_monitor/windows_agent/guard_agent.py`
  - PostgreSQL 数据库 `xmatrix.profile_state`
- **修改原因**：
  系统进入不可修复的混乱状态，profile_state 表中积压大量错误/垃圾数据，需彻底清空并禁用自动同步机制，改为手动控制。
- **修改内容摘要**：
  1. 通过 SSH 执行 `TRUNCATE TABLE profile_state RESTART IDENTITY`，清空所有实例状态数据
  2. 在 `guard_agent.py` 的 `run()` 方法中注释掉 `sync_windows()` 调用，防止 GuardAgent 自动写入垃圾数据
- **验证结果**：
  - `SELECT COUNT(*) FROM profile_state` 返回 `0`，数据库已清空
  - `guard_agent.py` 第 273-275 行已注释，`sync_windows()` 不再被自动调用
- **是否更新版本号**：本次为运维清理操作，未修改 Chrome 扩展，暂不更新 manifest 版本号

### 修改记录 2026-05-07（彻底清理 - 重启容器与内存缓存）

- **修改时间**：2026-05-07
- **修改文件**：
  - PostgreSQL 数据库 `xmatrix.profile_state`
  - NAS Docker 容器 `xmatrix_test_server`
- **修改原因**：
  测试数据污染系统，Dashboard 显示重复卡片，GuardAgent 积压 40+ pending_actions 导致疯狂重启窗口。需彻底清空数据库并重启容器清除 Flask 内存缓存。
- **修改内容摘要**：
  1. 通过 SSH 执行 `TRUNCATE TABLE profile_state RESTART IDENTITY`，清空所有实例状态数据
  2. 通过 SSH 执行 `docker compose restart` 重启 NAS 容器，清除 Flask 内存中的 `matrix_radar_pool`、`worked_targets_set`、`current_day_stats`、`account_tags`
  3. 容器启动时自动清空所有 `pending_actions`（V11.7.4 推倒重来逻辑触发）
- **验证结果**：
  - `SELECT COUNT(*) FROM profile_state` 返回 `0`，数据库已清空
  - 容器日志显示：`[启动清理] ✓ 内存数据已清空 (matrix_radar_pool, worked_targets_set, current_day_stats, account_tags)`
  - 容器日志显示：`[启动清理] 已清空所有 pending_actions（V11.7.4 推倒重来）`
  - 容器日志显示：`[数据库] PostgreSQL 表初始化完成`，表结构保留
  - 容器状态：`xmatrix_test_server` 已正常启动
- **是否更新版本号**：本次为运维清理操作，未修改 Chrome 扩展，暂不更新 manifest 版本号

### 修改记录 2026-05-07（test_nas_api.py 改为只读模式）

- **修改时间**：2026-05-07
- **修改文件**：
  - `x_matrix_nas/test_nas_api.py`
- **修改原因**：
  测试脚本 `test_nas_api.py` 频繁写入测试数据（如 `test-window-id-abc123`）到 `profile_state`，导致 GuardAgent 误判并尝试用假 ID 控制窗口，严重污染数据库。
- **修改内容摘要**：
  1. 将 `test_nas_api.py` 改为只读模式，禁止其写入任何测试数据到数据库
  2. 保留读取/查询功能，用于验证 NAS API 连通性
- **验证结果**：
  - `test_nas_api.py` 执行后不再产生 `test-window-id-*` 等垃圾数据
  - 执行 `TRUNCATE TABLE profile_state RESTART IDENTITY` 后，因扩展/GuardAgent 实时上报，表中保留 1 条活跃真实记录（`@badman1161#ad9368`），无测试污染数据
- **是否更新版本号**：未修改 Chrome 扩展 manifest，暂不更新版本号

---

### 修改记录 2026-05-07（V11.8.0 成功验证 - GuardAgent 扫描 remark 绑定模型）

- **修改时间**：2026-05-07
- **版本号**：V11.8.0（扩展）、V2.0（GuardAgent）
- **修改文件**：
  - `X-Matrix-Bot/content_id_extractor.js`
  - `X-Matrix-Bot/manifest.json`
  - `X-Matrix-Bot/options.html`
  - `x_matrix_nas/server.py`
  - `x_matrix_nas/database.py`
  - `scrm_monitor/windows_agent/guard_agent.py`
- **修改原因**：
  旧方案中扩展上报 window_id 不可靠（BitBrowser 过滤 console.log、Twitter 302 重定向丢失 URL hash），导致 GuardAgent 随机选窗口，多开场景会错乱。改用 GuardAgent 主动扫描 BitBrowser 窗口列表，读取 remark 字段建立 handle -> window_id 映射，扩展只上报 handle + 心跳。
- **修改内容摘要**：
  1. **数据库简化**：删除 profile_state 表的 window_id、window_short_id、archived 字段
  2. **GuardAgent V2.0 重写**：
     - `scan_windows()` 每 60 秒扫描 BitBrowser `/browser/list`
     - 读取窗口 `id`（UUID）和 `remark`（用户填写的 Twitter 账号名）
     - 建立 `handle -> window_id` 映射，同步到 NAS `/api/sync-windows`
     - `execute_action()` 根据 handle 查找 window_id，精确控制窗口
  3. **扩展简化**：
     - 删除 window_id 相关上报逻辑
     - profile_id 格式改为 `@handle#instanceId`（随机 9 位，用于区分多开）
     - 上报 payload 只包含 handle、profile_id、url、timestamp
  4. **Dashboard 简化**：去掉 window_id 显示，只显示 handle 和状态
- **验证结果**：
  - GuardAgent 日志：`[扫描] Badman1161 -> 9cf84d493d6a4c0c... (status=1)`
  - GuardAgent 日志：`[同步] NAS 映射更新成功: 1 个窗口`
  - Dashboard 显示 1 个 `@Badman1161` 卡片
  - 点击停止/启动/重启按钮，窗口正常关闭和打开
  - 多轮扫描稳定，映射不丢失
- **是否更新版本号**：✅ 是，manifest.json 11.7.7 → 11.8.0，GuardAgent V1.0 → V2.0
- **遗留问题**：
  1. 需要用户在 BitBrowser 中手动设置 remark，实例多时不方便
  2. 下一步：GuardAgent 自动设置 remark（通过 BitBrowser `/browser/update` API）

### 修改记录 2026-05-08（V11.9.0 终端统一上报架构）

- **修改时间**：2026-05-08
- **版本号**：V11.9.0（扩展）、V2.3（GuardAgent）
- **修改文件**：
  - `scrm_monitor/windows_agent/guard_agent.py` - FastAPI HTTP 服务重构
  - `X-Matrix-Bot/background.js` - 双模式路由（GuardAgent 优先，NAS fallback）
  - `X-Matrix-Bot/content_id_extractor.js` - 直接 fetch GuardAgent
  - `X-Matrix-Bot/content_follow.js` - 统一 `@handle#guard` 格式
  - `X-Matrix-Bot/content_chat.js` - 统一 `@handle#guard` 格式
  - `X-Matrix-Bot/config.js` - 新增 GUARD_AGENT_URL 配置
  - `x_matrix_nas/server.py` - 新增 `/api/guard/sync` 接口，废弃 `/report`
  - `x_matrix_nas/database.py` - profile_state 新增 window_id/stats_json/engine 列
  - `x_matrix_nas/templates/home.html` - Dashboard 只显示 profiles
- **修改原因**：
  旧架构中扩展直连 NAS，导致 workers 和 profiles 数据分散，Dashboard 同一账号显示多个卡片。改为 GuardAgent 作为唯一数据汇聚点，扩展只向 GuardAgent 上报，GuardAgent 统一同步 NAS。
- **修改内容摘要**：
  1. **GuardAgent V2.3**：新增 FastAPI HTTP 服务（端口 54346），接收扩展上报
  2. **扩展双模式路由**：GuardAgent 优先，NAS 自动降级
  3. **统一 profile_id 格式**：`@handle#guard`，移除随机 instanceId
  4. **NAS 新增 `/api/guard/sync`**：接收 GuardAgent 批量同步
  5. **废弃 `/report` 端点**：扩展不再直连 NAS
  6. **Dashboard 简化**：只显示 profiles，清空 workers
  7. **PostgreSQL 数据库**：容器使用 PostgreSQL（DB_TYPE=postgresql）
- **验证结果**：
  - GuardAgent 日志：`[Sync] NAS /api/guard/sync 成功: 1 profiles, 0 logs`
  - Dashboard 显示 1 个 `@badman1161#guard` 卡片，状态 active
  - 没有旧的重复卡片
  - 扩展显示 `✅ GuardAgent上报成功!`
- **是否更新版本号**：✅ 是，manifest.json → V11.9.0，GuardAgent → V2.3

### 修改记录 2026-05-08（V11.9.1 Dashboard 路由修复 + 大小写去重）

- **修改时间**：2026-05-08
- **版本号**：V11.9.1
- **修改文件**：
  - `x_matrix_nas/server.py` - 路由修复、Dashboard 去重、cleanup 接口
  - `x_matrix_nas/database.py` - profile_state 新增 window_id/stats_json/engine 列
  - `scrm_monitor/windows_agent/guard_agent.py` - handle 统一小写、heartbeat 支持 worker_id 提取
- **修改原因**：
  1. Dashboard 路由混乱：`/` 和 `/dashboard` 渲染的模板搞反了
  2. PostgreSQL 大小写敏感：`Badman1161` 和 `badman1161` 被视为不同 handle，导致重复卡片
  3. 扩展心跳 payload 使用 `worker_id` 而非 `handle`，GuardAgent 无法识别
  4. 数据库缺少 `window_id`/`stats_json`/`engine` 列
- **修改内容摘要**：
  1. **路由修复**：`/` → `index.html`（主页），`/dashboard` → `home.html`（运营大屏）
  2. **大小写去重**：Dashboard 查询使用 `DISTINCT ON (LOWER(handle))`，GuardAgent 统一使用小写 handle
  3. **heartbeat 修复**：GuardAgent `handle_heartbeat` 支持从 `worker_id`（`@handle#guard`）提取 handle
  4. **数据库迁移**：`profile_state` 新增 `window_id`、`stats_json`、`engine` 列
  5. **cleanup 接口**：新增 `/api/cleanup-profiles` 清理重复/无效记录
  6. **PostgreSQL 清理**：删除 11 条旧记录（各种随机 instanceId）
- **验证结果**：
  - GuardAgent 日志：`[Heartbeat] handle=badman1161 匹配到窗口 9cf84d493d6a4c0c...`
  - GuardAgent 日志：`[Sync] NAS /api/guard/sync 成功: 1 profiles, 0 logs`
  - PostgreSQL 数据库：`@badman1161#guard` 记录存在，status=active，engine=follow
- **遗留问题**：
  1. Dashboard 路由可能需要多次重启容器才能生效（Docker 缓存）
  2. 扩展心跳每 5 秒一次，但 GuardAgent 同步到 NAS 每 15 秒一次，Dashboard 刷新有延迟
- **是否更新版本号**：✅ 是，manifest.json → V11.9.1

### 修改记录 2026-05-08（V11.9.1 Dashboard 路由与模板问题排查）

- **修改时间**：2026-05-08
- **版本号**：V11.9.1
- **修改文件**：
  - `x_matrix_nas/server.py` - 路由配置
  - `x_matrix_nas/templates/index.html` - 移除实例卡片代码
  - `x_matrix_nas/templates/home.html` - 运营大屏模板
- **修改原因**：
  Dashboard 路由混乱，用户反馈 `/` 和 `/dashboard` 显示内容反了。
- **排查结果**：
  1. **路由配置已确认正确**：`/` → `index.html`，`/dashboard` → `home.html`
  2. **index.html 已清理**：移除了实例卡片相关代码（action-btns、sendAction、batchAction 等），仅保留表格视图
  3. **home.html 保持不变**：包含完整的实例卡片渲染逻辑（loadInstances、instance-card 等）
  4. **数据库使用 PostgreSQL**：`DB_TYPE=postgresql`，大小写敏感
  5. **profile_state 表已清理**：删除了旧的随机 instanceId 记录
- **当前状态**：
  - GuardAgent V2.3 正常运行（FastAPI HTTP 服务，端口 54346）
  - 扩展心跳正常上报到 GuardAgent
  - GuardAgent 同步到 NAS：`[Sync] NAS /api/guard/sync 成功: 1 profiles, 0 logs`
  - PostgreSQL 数据库：`@badman1161#guard` 记录存在，status=active
- **遗留问题**：
  1. `index.html` 仍然是"情报决策大屏"，不是用户想要的"简单主页（只有链接）"
  2. 用户想要 `/` 显示简单的链接页面（指向其他容器），`/dashboard` 显示运营大屏
  3. 需要创建一个新的简单主页模板，或修改 `index.html` 为简单链接页面
- **下一步**：
  1. 创建简单的主页模板（只有链接到其他容器）
  2. 或修改 `index.html` 移除 worker 数据表格，只保留链接
  3. 确保 `/dashboard` 正确显示实例卡片
- **是否更新版本号**：待定

---

## 9. 开发行为规范（强制）

### 9.1 每次修改必须执行

1. **更新版本号**
   - manifest.json 中的 `"version"` 必须递增
   - 格式：`主版本.次版本.修订号`（如 11.7.4 → 11.7.5）
   - 任何文件修改都算一次修订

2. **更新描述**
   - manifest.json 中的 `"description"` 必须以 `V{版本号} |` 开头
   - 描述中必须包含本次修改的核心内容（一句话概括）
   - 保留历史重要修改的简述（不超过 3 个旧项）

3. **记录到知识库**
   - 在 `X-MATRIX-KB.md` 第 8 节（修改记录）追加条目
   - 记录内容：时间、版本、修改文件、修改原因、验证结果

4. **同步到运行环境**
   - 修改源文件（opencode/ 目录）后，必须同步到实际运行目录
   - Chrome 扩展：必须重新加载（chrome://extensions → 重新加载）
   - NAS 后端：必须同步到 NAS 并重启容器
   - GuardAgent：必须重启进程

### 9.2 修改前必须检查

1. **读取知识库** - 确认当前系统状态，避免重复踩坑
2. **确认运行目录** - 确认 Chrome 扩展实际加载的是哪个目录
3. **确认版本号** - 当前运行版本 vs 最新代码版本是否一致

### 9.3 禁止行为

1. **禁止不更新版本号就修改代码**
2. **禁止不记录就修改关键逻辑**
3. **禁止在混乱状态下继续修修补补**（应该推倒重来或回滚）
4. **禁止忽略知识库中的已知问题**

### 9.4 推倒重来流程

当系统进入不可修复的混乱状态时：

1. 停止所有服务（GuardAgent + NAS）
2. 备份关键数据（如有必要）
3. 清空/重建数据库
4. 禁用自动机制（改为手动）
5. 单窗口端到端验证
6. 逐步恢复功能

---

## 10. 推倒重来操作记录

### 步骤 1：完全清理（执行于 2026-05-07）

- [x] 修改时间：2026-05-07
- [x] 操作内容：
  1. **停止 GuardAgent**：用户已在本地手动关闭
  2. **停止 NAS Docker 容器**：`docker compose down` 成功停止并移除 `xmatrix_test_server` 容器
  3. **清空数据库所有表**：
     - `profile_state`：0 条记录
     - `operation_log`：0 条记录
     - `action_logs_20260505`：0 条记录
     - `action_logs_20260506`：0 条记录
     - `daily_stats_20260505`：0 条记录
     - `daily_stats_20260506`：0 条记录
- [x] 验证结果：所有表 COUNT(*) 均为 0，数据库已彻底清空但表结构保留
- [x] 下一步：等待步骤 2（简化设计 + 重新验证）

---

## 11. 比特浏览器(BitBrowser) 操作说明

### 11.1 环境列表界面

从用户截图可见的列：
- **序号**：环境编号（如 10, 11, 12）
- **分组**：未分组
- **窗口名称**：显示名称（如 "Badman1161", "_1", "_2"）
- **代理IP**：代理服务器地址
- **标签**：（可自定义标签）
- **备注(remark)**：关键字段，用于绑定 Twitter 账号名
- **创建时间**：环境创建时间
- **配置**：Windows 配置图标
- **打开**：蓝色"打开"按钮，或已打开状态（眼睛图标）

### 11.2 设置备注(remark)

操作步骤：
1. 在环境列表中找到目标环境
2. 点击右侧的 **⋮**（三个点）菜单 或 右键
3. 选择 "编辑" 或 "修改环境"
4. 在弹出的编辑窗口中，找到 **"备注"** 字段
5. 填写 Twitter 账号名，例如：`Badman1161`
6. 点击 **保存**

**注意**：
- 备注字段在列表中显示为"备注"列
- 如果备注列不可见，可能需要右键列表标题栏勾选显示

### 11.3 BitBrowser Local API

**基础地址**：`http://127.0.0.1:54345`

**GuardAgent 使用的接口**：

#### 11.3.1 获取窗口列表
```
POST /browser/list
Payload: {"page": 0, "pageSize": 100}
Response: {
  "success": true,
  "data": {
    "totalNum": 10,
    "list": [
      {
        "id": "uuid",
        "name": "窗口名称",
        "remark": "备注",
        "status": 0/1,
        ...
      }
    ]
  }
}
```

#### 11.3.2 打开窗口
```
POST /browser/open
Payload: {"id": "uuid", "args": ["https://x.com/home"]}
```

#### 11.3.3 关闭窗口
```
POST /browser/close
Payload: {"id": "uuid"}
```

#### 11.3.4 更新窗口信息（设置备注）
```
POST /browser/update
Payload: {"id": "uuid", "remark": "Badman1161"}
Response: {"success": true/false, "msg": "..."}
```

**注意**：`/browser/update` 接口可能需要 `browserFingerPrint` 字段，具体取决于 BitBrowser 版本。

### 11.4 与 X-Matrix 集成要点

| BitBrowser 概念 | X-Matrix 对应 |
|----------------|--------------|
| 环境(environment) | Twitter 窗口实例 |
| 窗口名称(name) | 显示名称（可改） |
| 备注(remark) | **Twitter 账号名（关键绑定字段）** |
| UUID(id) | 窗口唯一标识（GuardAgent 控制用） |
| 状态(status) | 0=关闭, 1=运行中 |

### 11.5 常见问题

**Q: 备注在哪里设置？**
A: 环境列表 → 右键环境 → 编辑 → 找到"备注"字段。

**Q: 为什么 GuardAgent 读不到备注？**
A: 可能原因：
1. 备注填到了"窗口名称"而不是"备注"列
2. BitBrowser API 返回的字段名不同（某些版本可能叫 `remark`，某些可能叫 `note`）
3. API 分页问题（需要 `page: 1` 而不是 `page: 0`）

**Q: 如何确认 API 正常工作？**
A: 运行 GuardAgent 目录下的 `debug_api.py`，查看返回的数据结构。

---

*本文件由 X-Matrix 全栈程序员维护，作为项目单一事实来源 (Single Source of Truth)。
