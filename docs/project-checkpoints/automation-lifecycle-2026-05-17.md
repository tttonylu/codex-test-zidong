# Automation Lifecycle Checkpoint

## 目标
- 跑通 `terminal agent -> claim task -> running -> worker execute -> result report` 主链。

## 阶段
- 当前阶段：自动化执行链路校正

## 核心问题
- terminal 从 NAS 取回任务时，丢失了 `retry_limit / close_after_actions / requested_by / metadata`。
- `running` 状态之前是在 worker 执行完成后才上报，生命周期顺序错误。
- 执行 demo 使用共享 state，历史数据会污染验证结果。

## 实现决策
- `terminal_agent.runtime.agent_loop` 改成先 `prepare_execution`，先上报 `running`，再 `finish_execution` 上报结果。
- `terminal_agent.scripts.workers` 拆成 `prepare_execution / finish_execution / execute` 三段。
- 执行 demo 改用独立 state 文件并在结束后清理。

## 验证
- `python -m terminal_agent.demo_execution_loop`
- `python -m terminal_agent.demo_task_lifecycle`
- `python -m compileall nas_control_plane terminal_agent shared`

## 当前结论
- `running -> result` 顺序已正确。
- `close_after_actions` 已真实执行并回写结果。
- task 关键字段已完整透传到 terminal worker 侧。

## 后续建议
- 下一步优先做失败路径自动化验证：比如 open 失败、close 失败、unsupported script、missing instance_id。
