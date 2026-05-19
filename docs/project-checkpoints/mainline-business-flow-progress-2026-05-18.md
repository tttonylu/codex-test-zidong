# 涓荤嚎涓氬姟娴佹帹杩涜褰?
## 鏈疆鐩爣

鍦ㄤ笉缁х画鏀归〉闈㈢殑鍓嶆彁涓嬶紝浼樺厛鎺ㄨ繘涓氬姟涓荤嚎锛?
- NAS 鐩存帴涓嬪彂涓氬姟浠诲姟鍗?- 缁堢鎸夊姩浣滀覆鎵ц
- NAS 鏀跺埌涓氬姟缁撴灉
- 鎻掍欢妗ラ€愭瀵归綈瀹屾暣浠诲姟杞借嵎

## 宸插畬鎴?
### 1. NAS 鐩村彂涓氬姟浠诲姟鍗?
宸叉敮鎸佺洿鎺ュ垱寤猴細

- `account_id`
- `target`
- `action_plan`
- `campaign_id`
- `copy_payload`
- `terminal_id / instance_id`

涓嶅啀寮哄埗渚濊禆寮硅嵂姹犮€?
楠岃瘉锛?
- `python -m nas_control_plane.demo_direct_business_dispatch`

### 2. 缁堢鍔ㄤ綔涓查『搴忔墽琛?
缁堢鎵ц灞傚凡浠庘€滃崟鑴氭湰浠诲姟鈥濇帹杩涘埌鈥滃悓涓€浠诲姟鍐呮寜鍔ㄤ綔涓查『搴忔墽琛屸€濄€?
褰撳墠宸查獙璇佸姩浣滈摼锛?
- `follow -> icebreaker -> ad`

楠岃瘉锛?
- `python -m terminal_agent.demo_action_plan_business_flow`

### 3. 绔埌绔富绾垮啋鐑?
宸插畬鎴愪富绾垮啋鐑燂細

- NAS 鐩村彂涓氬姟鍗?- terminal claim
- instance 鎵挎帴
- action_plan 椤哄簭鎵ц
- NAS 鏀跺埌瀹屾暣缁撴灉

楠岃瘉锛?
- `python -m terminal_agent.demo_mainline_business_flow`

褰撳墠缁撴灉瑕佺偣锛?
- `dispatch_accepted = true`
- `task_status = completed`
- `dispatch_origin = nas_direct`
- `business_kind = account_target_action_plan`
- `action_result_count = 3`

### 4. 鎻掍欢 fetch_task 鍏煎鎺ㄨ繘

宸插湪鎻掍欢 background 妗ヤ腑澧炲姞瀹屾暣浠诲姟缂撳瓨锛?
- `matrix_current_task`
- `matrix_current_task_id`
- `matrix_current_action_plan`
- `matrix_current_target`
- `matrix_current_copy_payload`

鐩殑锛?
- 涓嶇牬鍧忔棫鎻掍欢浠嶄緷璧栫殑 `creator` 杩斿洖鍊?- 鍚屾椂涓哄悗缁唴瀹硅剼鏈縼绉诲埌瀹屾暣涓氬姟浠诲姟璇箟鍋氬噯澶?
## 褰撳墠杩樻病瀹屾垚

1. 鍐呭鑴氭湰浠嶄富瑕佹寜鈥滃彧鎷?creator 瀛楃涓测€濊繍琛?2. 鎻掍欢鏃х殑 `log_action / send_report / report_user_id` 杩樻病瀹屽叏缁熶竴鎴愪笟鍔′换鍔¤涔?3. NAS 椤甸潰铏界劧宸叉湁涓荤嚎鍏ュ彛锛屼絾鏈疆鏈户缁獙鏀堕〉闈㈠睍绀?
## 涓嬩竴姝?
涓嬩竴姝ヤ紭鍏堝仛锛?
1. 鍐呭鑴氭湰娑堣垂 `matrix_current_task`
2. 鎻掍欢鍔ㄤ綔涓婃姤涓?`task_id / action_plan` 缁戝畾
3. 鎻掍欢鐪熷疄閾捐矾瀵归綈 `璐﹀彿 + 鐩爣 + 鍔ㄤ綔涓瞏

### 5. 插件阶段结果已开始同步回 NAS 任务语义
已补上最小桥接：
- `/plugin/action-log` 在保留每日统计聚合的同时
- 若 `metadata.task_id` 存在，会同步写入对应 NAS task 的 `parameters.result_details.action_results`
- 当前已记录：
  - `action`
  - `status`
  - `summary`
  - `action_index`
  - `details`

验证：
- `python -m nas_control_plane.demo_plugin_action_log_task_stage_sync`

当前结果要点：
- task 仍保持 `queued/running/completed` 主生命周期不被插件阶段日志直接改写
- 但任务对象内部已经能看到插件阶段动作结果
- 这是从“只有 daily stat”到“任务阶段结果可回看”的第一步

### 6. 任务内部已补业务动作进度摘要
在插件阶段结果写入 task 的基础上，task `parameters.result_details` 现已补充：
- `planned_action_count`
- `completed_action_count`
- `failed_action_count`
- `business_progress_status`

当前业务进度状态最小语义：
- `in_progress`
- `partially_completed`
- `action_failed`
- `partial_failure`
- `action_plan_completed`

验证：
- `python -m nas_control_plane.demo_plugin_action_log_task_stage_sync`

当前结果要点：
- 不改 task 主生命周期
- 但 NAS 侧已能直接看出一个业务动作单执行到了哪一段、是否部分失败
