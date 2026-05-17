# NAS Web Console Checkpoint

## 目标
- 给 NAS 管理面补齐查询、详情、重试和终端联动能力。

## 阶段
- 当前阶段：web-console 可操作化
- 前序阶段：SQLite 持久化与 task-management 底座

## 分支
- 主线：`main`
- 相关历史分支：`codex/nas-web-console`, `codex/sqlite-persistence`

## 接口
- `GET /dashboard`
- `GET /terminals`
- `GET /instances`
- `GET /tasks`
- `GET /logs`
- `GET /task/{task_id}`
- `GET /terminal/{terminal_id}`
- `GET /instance/{instance_id}`
- `POST /tasks/retry`

## 实现决策
- 把 dashboard HTML 拆到 `nas_control_plane/dashboard_html.py`，避免继续维护乱码块。
- `terminal_agent.adapters.nas_client` 增加终端/实例查询参数透传。
- CLI 使用同一套查询接口，避免页面和命令行行为分裂。

## 验证
- `python -m compileall nas_control_plane terminal_agent shared`

## 未完成项
- 浏览器里验证 `/dashboard` 的筛选、详情、重试联动。
- 如有需要，再补更细的终端侧状态展示和错误码视图。

## 后续建议
- 优先做浏览器验证和 git 提交，然后继续下一层的 terminal 行为联动。
