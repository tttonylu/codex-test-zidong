# 插件任务对象兼容桥记录

## 目的

在不立刻重写旧插件内容脚本的前提下，让插件开始接收完整业务任务对象。

## 当前处理方式

### background.js

`fetch_task` 在收到 GuardAgent `/plugin/task/pull` 返回后，除了保留旧的：

- `response.data = creator`

还会把完整任务缓存到：

- `matrix_current_task`
- `matrix_current_task_id`
- `matrix_current_action_plan`
- `matrix_current_target`
- `matrix_current_copy_payload`

### content_follow.js

在 `FETCH` 阶段：

- 仍兼容旧的 `rawCreator`
- 但如果 `response.task` 存在，会将完整任务缓存到：
  - `matrix_current_task`
  - `matrix_current_task_id`
  - `matrix_current_action_plan`
  - `matrix_current_target_payload`
  - `matrix_current_copy_payload`

并优先使用 `task.target.handle` 作为当前目标。

## 意义

这一步不是最终形态，但它完成了一个关键过渡：

- 旧插件脚本不至于立即失效
- 新主线业务任务对象已经能进入插件本地状态
- 后续可以继续把内容脚本从“creator 字符串驱动”迁移到“完整任务驱动”

## 还没完成

1. `content_chat.js` 还未消费完整 `matrix_current_task`
2. 插件动作上报还未完全绑定 `task_id`
3. 插件尚未严格按 `action_plan` 驱动页面动作分支
