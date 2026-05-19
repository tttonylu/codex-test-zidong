# System Purpose And Requirements Baseline

## 1. 文档目的

这份文档定义 `codex-matrix-bplus` 当前阶段的核心目标、需求边界和实现约束。

后续无论是 NAS 管理面、terminal agent、worker、查询接口、恢复策略，还是 dashboard，都应以这份文档作为基线。

如果某个实现和这份基线冲突，应优先回到这里校正方向，而不是继续堆功能。

## 2. 系统核心目的

这个系统的核心目的，不是单纯“写几个自动化脚本”，而是建立一套：

- 可调度
- 可观测
- 可恢复
- 可扩展

的多终端、多实例、多任务自动化执行系统。

一句话总结：

> 我们要做的不是脚本集合，而是一个中心控制、多终端执行、统一状态回报的自动化控制系统。

## 3. 为什么要做这个系统

旧体系的问题，不是“功能不够多”，而是“能力分散、状态割裂、失败不可控、扩展成本高”。

典型问题包括：

- 执行逻辑散落在扩展、本地脚本、窗口控制和后端之间
- 哪个账号对应哪个实例、哪个窗口，不稳定也不透明
- 任务执行后的结果缺乏统一语义，失败无法标准化处理
- 多终端、多实例场景下，很难靠人工维持一致性
- 页面、执行、调度、状态经常耦合在一起，导致修改一个点就影响整条链路

因此，新系统的建设目标是把这些能力收束成一套统一控制面和统一执行面。

## 4. 需求本质

当前阶段的核心需求不是“支持多少页面”，也不是“先把界面做完”，而是以下五件事：

1. 建立中心控制面
   NAS 必须能统一管理 terminal、instance、task、log、result，而不是只做被动展示。

2. 建立终端执行面
   每台 terminal 必须能独立注册、扫描实例、领取任务、执行 worker、上报状态。

3. 建立统一任务生命周期
   每个 task 都必须有明确的状态流转和失败语义，而不是只有“成功/失败”两个粗状态。

4. 建立统一恢复语义
   系统必须知道什么错误可以重试，什么错误必须终止，什么错误需要人工介入。

5. 建立可重复验证链路
   核心链路不能依赖口头判断，必须能通过 demo、脚本和状态输出来重复验证。

## 5. 当前阶段的优先级

当前优先级从高到低如下：

1. 自动化主链跑通
2. 失败路径与恢复语义跑通
3. 调度策略与执行策略完善
4. 查询与运营视图增强
5. 页面体验与展示优化

这意味着：

- dashboard 不是当前阶段的主目标
- 页面只服务于观测，不应反过来主导架构
- 只要页面不阻塞主链验证，就不应优先投入页面工作

## 6. 当前阶段必须成立的核心链路

当前系统至少必须稳定支持这条链路：

`NAS create task -> terminal claim -> running -> worker execute -> result report -> retry/final/cancel decision`

如果这条链路不成立，则系统不算“跑通”。

## 7. 当前阶段必须具备的能力

### 7.1 成功路径

系统必须能稳定完成至少这些 worker 的基础执行闭环：

- `follow`
- `chat`
- `probe`
- `extract`

这里的“完成”指的是：

- task 被正确 claim
- running 状态被正确上报
- worker 被正确调用
- result 被正确回报
- task 最终状态被正确落库

### 7.2 失败路径

系统必须能稳定覆盖并区分至少这些失败路径：

- `bitbrowser.request_failed`
- `bitbrowser.open_failed`
- `bitbrowser.close_failed`
- `worker.missing_instance_id`
- `worker.missing_bitbrowser_client`
- `worker.unsupported_script`

### 7.3 生命周期语义

任务状态不能只停留在“成功/失败”，而应至少区分：

- `queued`
- `dispatched`
- `running`
- `completed`
- `retry_pending`（兼容别名）
- `manual_retry_pending`
- `terminal_recovery_pending`
- `retryable_failure`
- `terminal_failure`
- `cancelled`

## 8. 当前阶段的实现约束

### 8.1 控制面与执行面分离

- NAS 负责调度、状态、记录、策略
- terminal 负责本地实例扫描、任务执行、结果上报
- worker 只负责一个 task 的执行逻辑
- 页面不承担调度职责

### 8.2 错误必须结构化

错误不能只存字符串，至少要包含：

- `error_code`
- `error_message`
- `retryable`
- `final`
- 必要的 `details`

### 8.3 重试必须有明确边界

- 可重试失败进入 `retryable_failure`
- 进入人工重试队列后使用 `manual_retry_pending`
- 终端重启恢复回收后使用 `terminal_recovery_pending`
- 兼容历史状态读取与查询时保留 `retry_pending` 作为别名
- 超出 retry 上限后进入 `terminal_failure`
- 被阻止的重试必须记录 `retry_blocked_reason`
- 已到可领取时间但因 terminal 槽位不足未被领取时，应保留真实等待原因，例如 `slot_capacity_reached`，而不是误记为 `retry_not_ready`

### 8.4 取消必须有明确边界

- 只能取消未完成任务
- 已终态任务拒绝取消
- 被阻止的取消必须记录 `cancel_blocked_reason`

### 8.5 验证脚本必须隔离

所有 demo / 验证脚本应尽量使用独立状态文件并在结束后清理，避免历史状态污染结果。

## 9. 当前阶段不应做的事

在核心链路未稳定前，不应优先投入这些方向：

- 大量美化 dashboard
- 过早做复杂前端交互
- 把页面当成控制中枢
- 在没有统一错误语义前堆更多 worker 行为
- 在没有清晰任务状态机前做复杂运营逻辑

## 10. 当前阶段的完成标准

当前阶段可以认为“基本成立”，至少要满足：

1. 成功路径有稳定 demo 可重复验证
2. 失败路径有稳定 demo 可重复验证
3. 任务生命周期顺序正确
4. 关键字段透传完整
5. retry / cancel / final 语义明确
6. NAS 能查询 task / terminal / log / result
7. 所有判断不是靠页面猜测，而是能从状态与结果中直接验证

## 11. 后续阶段方向

当当前阶段成立后，下一阶段应优先进入：

- 按错误码分流的恢复策略
- 更真实的 terminal 调度策略
- 多任务执行顺序与执行槽位控制
- 更细的结果归档与审计
- 更强的运营与查询视图

当前主线已经进入其中的“更真实的 terminal 调度策略 / 多任务执行顺序与执行槽位控制”，重点是：

- terminal 真并发 worker / slot 对象模型
- slot 亲和性与恢复后重新派发
- NAS 侧恢复任务优先级与查询面联动

## 12. 一句话约束

后续所有实现，都应优先回答这个问题：

> 这项改动是在让系统更接近“可调度、可观测、可恢复的自动化控制系统”，还是只是在增加表面功能？

如果只是增加表面功能，而没有增强核心链路，应降低优先级。
