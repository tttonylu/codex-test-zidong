"""Standalone dashboard HTML for the NAS web console."""

DASHBOARD_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NAS Web Console</title>
  <style>
    :root {
      --bg: #f3efe6;
      --panel: #fffaf0;
      --panel-2: #f7f1e4;
      --panel-3: #f0e6d4;
      --ink: #1d2a32;
      --muted: #6b7278;
      --line: #d9cfbd;
      --brand: #0d6b66;
      --brand-2: #d76f30;
      --warn: #b14623;
      --ok: #2c6e49;
      --danger: #c0392b;
      --shadow: 0 12px 32px rgba(25, 37, 44, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at top right, rgba(215,111,48,0.14), transparent 30%),
                  radial-gradient(circle at left center, rgba(13,107,102,0.12), transparent 25%),
                  var(--bg);
    }
    .page { max-width: 1440px; margin: 0 auto; padding: 28px 20px 48px; }
    .hero { display: grid; gap: 14px; margin-bottom: 20px; }
    .hero h1 { margin: 0; font-size: 34px; line-height: 1.1; letter-spacing: -0.03em; }
    .hero p { margin: 0; color: var(--muted); max-width: 900px; }
    .stats { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 20px; }
    .stat, .panel {
      background: var(--panel); border: 1px solid var(--line);
      border-radius: 20px; box-shadow: var(--shadow);
    }
    .stat { padding: 16px 18px; }
    .stat .label { color: var(--muted); font-size: 13px; }
    .stat .value { font-size: 28px; margin-top: 6px; font-weight: 700; }
    .layout { display: grid; grid-template-columns: 1.2fr 1.1fr; gap: 18px; }
    .column { display: grid; gap: 18px; align-content: start; }
    .panel { padding: 16px; }
    .panel h2 { margin: 0 0 12px; font-size: 18px; }
    .panel h3 { margin: 0 0 10px; font-size: 15px; }
    .panel-head { display: flex; justify-content: space-between; align-items: start; gap: 12px; margin-bottom: 12px; }
    .toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
    input, select, button {
      border-radius: 12px; border: 1px solid var(--line);
      padding: 8px 12px; font: inherit; background: white;
    }
    input, select { min-width: 120px; }
    button {
      cursor: pointer; background: var(--brand); color: white; border-color: var(--brand);
    }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    button.secondary { background: var(--panel-2); color: var(--ink); border-color: var(--line); }
    button.warn { background: var(--brand-2); border-color: var(--brand-2); }
    button.danger { background: var(--danger); border-color: var(--danger); }
    button.card { color: inherit; text-align: left; width: 100%; }
    button.small { font-size: 12px; padding: 4px 10px; }
    .list { display: grid; gap: 10px; max-height: 520px; overflow: auto; padding-right: 4px; }
    .card {
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(247,241,228,0.95));
      border-radius: 16px; padding: 14px; display: grid; gap: 8px;
    }
    .card.active { border-color: var(--brand); box-shadow: inset 0 0 0 1px rgba(13,107,102,0.18); }
    .card.selected { border-color: var(--brand-2); background: rgba(215,111,48,0.06); }
    .card-header { display: flex; justify-content: space-between; gap: 12px; align-items: start; }
    .title { font-weight: 700; font-size: 15px; word-break: break-word; }
    .meta { color: var(--muted); font-size: 12px; }
    .badge-row { display: flex; flex-wrap: wrap; gap: 8px; }
    .badge {
      display: inline-flex; align-items: center; border-radius: 999px;
      padding: 4px 10px; font-size: 12px; border: 1px solid var(--line); background: white;
    }
    .badge.ok { color: var(--ok); border-color: rgba(44,110,73,0.24); }
    .badge.warn { color: var(--warn); border-color: rgba(177,70,35,0.24); }
    .detail-stack { display: grid; gap: 12px; }
    .detail-section {
      display: grid; gap: 8px; padding: 12px; border: 1px solid var(--line);
      border-radius: 16px; background: rgba(255, 255, 255, 0.7);
    }
    .kv-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .kv { display: grid; gap: 4px; padding: 10px; border-radius: 12px; background: var(--panel-3); }
    .kv .k { color: var(--muted); font-size: 12px; }
    .kv .v { font-size: 14px; word-break: break-word; }
    pre {
      margin: 0; white-space: pre-wrap; word-break: break-word;
      background: #fff; border: 1px solid var(--line); border-radius: 14px;
      padding: 12px; max-height: 260px; overflow: auto;
    }
    .muted { color: var(--muted); }
    .empty {
      color: var(--muted); border: 1px dashed var(--line); border-radius: 14px;
      padding: 18px; text-align: center; background: rgba(255,255,255,0.55);
    }
    .status-line { min-height: 22px; margin-top: 10px; color: var(--muted); font-size: 13px; }
    .field { display: grid; gap: 6px; }
    .field label { color: var(--muted); font-size: 12px; }
    .card-grid { display: grid; gap: 10px; }
    .hint { color: var(--muted); font-size: 12px; line-height: 1.6; }
    .instance-row { display: flex; align-items: center; gap: 10px; }
    .instance-row input[type="checkbox"] { min-width: auto; width: 18px; height: 18px; cursor: pointer; }
    .bl-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border: 1px solid var(--line); border-radius: 12px; background: white; }
    .bl-item .bl-target { font-weight: 600; }
    .bl-item .bl-reason { color: var(--muted); font-size: 12px; }
    .stats-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .stats-table th, .stats-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--line); }
    .stats-table th { color: var(--muted); font-size: 12px; }
    .tabs { display: flex; gap: 8px; margin-bottom: 12px; }
    .tabs button { background: var(--panel-2); color: var(--ink); border-color: var(--line); }
    .tabs button.active-tab { background: var(--brand); color: white; border-color: var(--brand); }
    .action-result { font-size: 13px; min-height: 24px; line-height: 24px; }
    @media (max-width: 960px) {
      .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .layout { grid-template-columns: 1fr; }
      .kv-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 640px) {
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .hero h1 { font-size: 28px; }
    }
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>矩阵自动化控制台</h1>
      <p>NAS — 统一下发任务 / 监控实例 / 管理弹药 / 查看统计 / 黑名单</p>
    </section>

    <section class="stats" id="summary-stats"></section>

    <section class="layout">
      <!-- ====== LEFT COLUMN ====== -->
      <div class="column">

        <!-- 弹药下发 -->
        <div class="panel">
          <div class="panel-head">
            <div><h2>弹药下发</h2><div class="hint">添加博主 ID 或链接到弹药库</div></div>
          </div>
          <div style="display:grid; gap:14px;">
            <div class="field">
              <label for="ammo-script-lane">脚本</label>
              <select id="ammo-script-lane">
                <option value="follow">自动关注 (content_follow.js)</option>
                <option value="chat">自动聊天 (content_chat.js)</option>
              </select>
            </div>
            <div class="field">
              <label for="ammo-target-input">目标 handle</label>
              <input id="ammo-target-input" placeholder="输入 handle，如 elonmusk" style="font-size:16px; padding:12px;">
            </div>
            <div class="field">
              <label for="ammo-creator-id">来源创作者 ID（可空）</label>
              <input id="ammo-creator-id" placeholder="留空自动使用目标 handle">
            </div>
            <div style="display:flex; gap:10px;">
              <button id="submit-ammo" style="flex:2; padding:12px; font-size:16px; font-weight:600;">添加弹药</button>
            </div>
            <div class="status-line" id="ammo-result">就绪。</div>
          </div>
        </div>

        <!-- 弹药库存 -->
        <div class="panel">
          <div class="panel-head">
            <div><h2>弹药库存</h2><div class="hint">分发状态一览</div></div>
            <button class="secondary small" id="reload-ammo-inventory">刷新</button>
          </div>
          <div class="tabs">
            <button data-tab="all" class="active-tab">全部</button>
            <button data-tab="available">可用</button>
            <button data-tab="assigned">已分配</button>
            <button data-tab="consumed">已消耗</button>
          </div>
          <div class="status-line" id="ammo-inventory-summary" style="margin-bottom:10px;">加载中...</div>
          <div class="list" id="ammo-inventory-list" style="max-height:260px;"></div>
        </div>

        <!-- 任务列表 -->
        <div class="panel">
          <h2>任务列表</h2>
          <div class="toolbar">
            <input id="filter-task-terminal" placeholder="terminal_id">
            <select id="filter-task-status">
              <option value="">全部状态</option>
              <option value="queued">queued</option>
              <option value="dispatched">dispatched</option>
              <option value="running">running</option>
              <option value="completed">completed</option>
              <option value="retryable_failure">retryable_failure</option>
              <option value="terminal_failure">terminal_failure</option>
              <option value="retry_pending">retry_pending</option>
              <option value="cancelled">cancelled</option>
            </select>
            <select id="filter-task-wait-reason">
              <option value="">全部等待原因</option>
              <option value="slot_capacity_reached">slot_capacity_reached</option>
              <option value="instance_blocked">instance_blocked</option>
              <option value="retry_not_ready">retry_not_ready</option>
            </select>
            <input id="filter-task-blocked-instance" placeholder="blocked_instance_id">
            <button id="reload-tasks">刷新任务</button>
          </div>
          <div class="list" id="task-list"></div>
        </div>

        <!-- 终端列表 -->
        <div class="panel">
          <h2>终端列表</h2>
          <div class="toolbar">
            <input id="filter-terminal-operator" placeholder="operator_name">
            <select id="filter-terminal-status">
              <option value="">全部状态</option>
              <option value="registered">registered</option>
              <option value="online">online</option>
              <option value="degraded">degraded</option>
              <option value="offline">offline</option>
            </select>
            <input id="filter-terminal-max-parallel" placeholder="max_parallel_tasks">
            <button class="secondary" id="reload-terminals">刷新终端</button>
          </div>
          <div class="list" id="terminal-list"></div>
        </div>
      </div>

      <!-- ====== RIGHT COLUMN ====== -->
      <div class="column">

        <!-- 实例管理 -->
        <div class="panel">
          <div class="panel-head">
            <div><h2>实例管理</h2><div class="hint">选择实例，执行操作</div></div>
          </div>
          <div class="toolbar">
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;">
              <input type="checkbox" id="select-all-instances" style="min-width:auto;width:16px;height:16px;"> 全选/取消
            </label>
            <button class="warn small" id="btn-auto-start">全自动启动</button>
            <button class="secondary small" id="btn-stop">停止</button>
            <button class="secondary small" id="btn-close">关闭</button>
            <button class="secondary small" id="btn-open">打开</button>
            <button class="secondary small" id="reload-instances">刷新</button>
          </div>
          <div class="action-result" id="instance-action-result"></div>
          <div class="card-grid" id="instance-managed-grid">
            <div class="empty">加载中...</div>
          </div>
        </div>

        <!-- 任务详情 -->
        <div class="panel">
          <h2>任务详情</h2>
          <div class="toolbar">
            <button class="secondary" id="cancel-task" disabled>取消</button>
            <button class="warn" id="retry-task" disabled>重试</button>
            <span class="muted" id="action-result">未执行动作</span>
          </div>
          <div class="detail-stack">
            <div class="detail-section">
              <h3>任务摘要</h3>
              <div class="kv-grid" id="task-summary-grid"></div>
            </div>
            <div class="detail-section">
              <h3>诊断信息</h3>
              <div class="kv-grid" id="task-diagnostics-grid"></div>
            </div>
            <div class="detail-section">
              <h3>结果详情</h3>
              <pre id="task-result-details">请选择左侧任务。</pre>
            </div>
            <div class="detail-section">
              <h3>任务原始记录</h3>
              <pre id="task-detail">请选择左侧任务。</pre>
            </div>
            <div class="detail-section">
              <h3>任务日志</h3>
              <pre id="task-logs">相关日志会显示在这里。</pre>
            </div>
          </div>
        </div>

        <!-- 脚本运行状态 -->
        <div class="panel">
          <h2>脚本运行状态</h2>
          <div class="card-grid">
            <div class="card" id="script-status-follow">
              <div class="card-header">
                <div><span class="title">自动关注 (follow)</span></div>
                <div class="badge" id="follow-status-badge">--</div>
              </div>
              <div class="meta" id="follow-run-detail">等待数据...</div>
            </div>
            <div class="card" id="script-status-chat">
              <div class="card-header">
                <div><span class="title">自动聊天 (chat)</span></div>
                <div class="badge" id="chat-status-badge">--</div>
              </div>
              <div class="meta" id="chat-run-detail">等待数据...</div>
            </div>
          </div>
        </div>

        <!-- 日报表 -->
        <div class="panel">
          <div class="panel-head">
            <div><h2>日报表</h2><div class="hint">按账号查看每日动作统计（保留15天）</div></div>
          </div>
          <div class="toolbar">
            <input type="date" id="daily-stats-date">
            <button class="secondary small" id="reload-daily-stats">查询</button>
            <button class="secondary small" id="cleanup-daily-stats">清理过期</button>
          </div>
          <div class="action-result" id="daily-stats-result"></div>
          <div style="max-height:300px;overflow:auto;">
            <table class="stats-table" id="daily-stats-table">
              <thead><tr><th>日期</th><th>账号</th><th>脚本</th><th>动作</th><th>成功</th><th>失败</th><th>总计</th></tr></thead>
              <tbody><tr><td colspan="7" class="empty">选择日期后点击查询</td></tr></tbody>
            </table>
          </div>
        </div>

        <!-- 黑名单 -->
        <div class="panel">
          <div class="panel-head">
            <div><h2>黑名单</h2><div class="hint">被拉黑的目标全账号自动跳过</div></div>
            <button class="secondary small" id="reload-blacklist">刷新</button>
          </div>
          <div style="display:flex; gap:10px; margin-bottom:10px;">
            <input id="bl-target-input" placeholder="handle（如 spammer123）" style="flex:2;">
            <input id="bl-reason-input" placeholder="原因（可选）" style="flex:1;">
            <button id="bl-add-btn" class="warn small">添加</button>
          </div>
          <div class="action-result" id="bl-action-result"></div>
          <div class="list" id="blacklist-list" style="max-height:240px;"></div>
        </div>

        <!-- 终端详情 -->
        <div class="panel">
          <h2>终端详情</h2>
          <div class="detail-stack">
            <div class="detail-section">
              <h3>终端信息</h3>
              <pre id="terminal-detail">请选择左侧终端。</pre>
            </div>
            <div class="detail-section">
              <h3>终端实例</h3>
              <pre id="terminal-instances">该终端的实例列表会显示在这里。</pre>
            </div>
          </div>
        </div>

      </div>
    </section>
  </div>

  <script>
    const state = { selectedTaskId: null, selectedTerminalId: null, tasks: [], terminals: [], instances: [], accounts: [], blacklist: [], ammoItems: [], dailyStats: [] };
    let selectedInstanceIds = new Set();

    // -- refs --
    const taskListEl = document.getElementById("task-list");
    const terminalListEl = document.getElementById("terminal-list");
    const taskDetailEl = document.getElementById("task-detail");
    const taskLogsEl = document.getElementById("task-logs");
    const taskSummaryGridEl = document.getElementById("task-summary-grid");
    const taskDiagnosticsGridEl = document.getElementById("task-diagnostics-grid");
    const taskResultDetailsEl = document.getElementById("task-result-details");
    const terminalDetailEl = document.getElementById("terminal-detail");
    const terminalInstancesEl = document.getElementById("terminal-instances");
    const cancelButtonEl = document.getElementById("cancel-task");
    const retryButtonEl = document.getElementById("retry-task");
    const actionResultEl = document.getElementById("action-result");
    const summaryStatsEl = document.getElementById("summary-stats");
    const instanceManagedGridEl = document.getElementById("instance-managed-grid");
    const instanceActionResultEl = document.getElementById("instance-action-result");
    const ammoResultEl = document.getElementById("ammo-result");
    const ammoInventorySummaryEl = document.getElementById("ammo-inventory-summary");
    const ammoInventoryListEl = document.getElementById("ammo-inventory-list");
    const blacklistListEl = document.getElementById("blacklist-list");
    const blActionResultEl = document.getElementById("bl-action-result");
    const dailyStatsTableEl = document.getElementById("daily-stats-table");
    const dailyStatsResultEl = document.getElementById("daily-stats-result");

    // -- event wiring --
    document.getElementById("submit-ammo").addEventListener("click", submitAmmo);
    document.getElementById("reload-tasks").addEventListener("click", () => loadTasks());
    document.getElementById("reload-terminals").addEventListener("click", () => loadTerminals());
    document.getElementById("reload-instances").addEventListener("click", () => loadSummaryStats());
    document.getElementById("reload-blacklist").addEventListener("click", () => loadBlacklist());
    document.getElementById("reload-ammo-inventory").addEventListener("click", () => loadAmmoInventory());
    document.getElementById("reload-daily-stats").addEventListener("click", () => loadDailyStats());
    document.getElementById("cleanup-daily-stats").addEventListener("click", cleanupDailyStats);
    document.getElementById("bl-add-btn").addEventListener("click", addBlacklistItem);

    document.getElementById("filter-task-status").addEventListener("change", () => loadTasks());
    document.getElementById("filter-task-wait-reason").addEventListener("change", () => loadTasks());
    document.getElementById("filter-terminal-status").addEventListener("change", () => loadTerminals());

    ["filter-task-terminal", "filter-task-blocked-instance", "filter-terminal-operator", "filter-terminal-max-parallel"].forEach(id => {
      document.getElementById(id).addEventListener("keydown", event => {
        if (event.key === "Enter") { loadTasks(); loadTerminals(); }
      });
    });

    cancelButtonEl.addEventListener("click", cancelSelectedTask);
    retryButtonEl.addEventListener("click", retrySelectedTask);

    document.getElementById("select-all-instances").addEventListener("change", toggleSelectAllInstances);
    document.getElementById("btn-auto-start").addEventListener("click", () => batchAction("auto_start"));
    document.getElementById("btn-stop").addEventListener("click", () => batchAction("stop"));
    document.getElementById("btn-close").addEventListener("click", () => batchAction("close"));
    document.getElementById("btn-open").addEventListener("click", () => batchAction("open"));

    document.querySelectorAll("#ammo-inventory-list").forEach(() => {});

    // Set default date to today
    const today = new Date().toISOString().slice(0, 10);
    document.getElementById("daily-stats-date").value = today;

    // -- utils --
    function escapeHtml(text) { return String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;"); }
    function stringifyBool(value) { if (value === true) return "true"; if (value === false) return "false"; return "-"; }
    function renderKv([key, value]) { return `<div class="kv"><div class="k">${escapeHtml(key)}</div><div class="v">${escapeHtml(value ?? "-")}</div></div>`; }

    async function fetchJson(path, options) {
      const response = await fetch(path, options);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "request failed");
      return data;
    }

    // -- summary stats --
    async function loadSummaryStats() {
      const [terminals, instances, tasks, accounts] = await Promise.all([
        fetchJson("/terminals"), fetchJson("/instances"), fetchJson("/tasks"), fetchJson("/plugin/accounts"),
      ]);
      state.terminals = terminals.items || [];
      state.instances = instances.items || [];
      state.tasks = tasks.items || [];
      state.accounts = accounts.items || [];
      renderSummaryStats();
      renderManagedInstances();
      renderScriptStatus();
    }

    function renderSummaryStats() {
      const onlineTerminals = state.terminals.filter(item => (item.status || "") !== "offline").length;
      const onlineInstances = state.instances.filter(item => (item.runtime_status || "") === "running").length;
      const availableAmmo = (state.accounts || []).filter(item => (item.status || "") === "available").length;
      const runningTasks = state.tasks.filter(item => ["queued", "dispatched", "running"].includes(item.status)).length;
      const blockedCount = state.blacklist.length;
      const items = [["在线终端", onlineTerminals], ["在线实例", onlineInstances], ["可用账号", availableAmmo], ["待执行任务", runningTasks], ["黑名单", blockedCount]];
      summaryStatsEl.innerHTML = items.map(([label, value]) => `<div class="stat"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(value)}</div></div>`).join("");
    }

    // -- managed instances --
    function renderManagedInstances() {
      instanceManagedGridEl.innerHTML = "";
      if (!state.instances.length) { instanceManagedGridEl.innerHTML = '<div class="empty">没有已同步的实例。</div>'; return; }
      for (const item of state.instances) {
        const metadata = item.metadata || {};
        const isSelected = selectedInstanceIds.has(item.instance_id);
        const card = document.createElement("div");
        card.className = "card" + (isSelected ? " selected" : "");
        card.innerHTML = `<div class="instance-row">
          <input type="checkbox" data-instance-id="${escapeHtml(item.instance_id)}" ${isSelected ? "checked" : ""}>
          <div style="flex:1;">
            <div class="title">${escapeHtml(item.remark || item.handle || item.instance_id)}</div>
            <div class="meta">${escapeHtml(item.instance_id)} / ${escapeHtml(item.terminal_id || "-")} / ${escapeHtml(metadata.instance_health_status || item.runtime_status || "-")}</div>
          </div>
          <div class="badge ${(item.runtime_status || "") === "running" ? "ok" : "warn"}">${escapeHtml(item.runtime_status || "-")}</div>
          <div class="badge">${escapeHtml(item.handle || "-")}</div>
        </div>`;
        card.querySelector("input[type=checkbox]").addEventListener("change", evt => {
          const iid = evt.target.dataset.instanceId;
          if (evt.target.checked) selectedInstanceIds.add(iid); else selectedInstanceIds.delete(iid);
          syncSelectAllCheckbox();
        });
        card.addEventListener("click", () => { /* absorb click on card */ });
        instanceManagedGridEl.appendChild(card);
      }
    }

    function syncSelectAllCheckbox() {
      const cb = document.getElementById("select-all-instances");
      cb.checked = selectedInstanceIds.size > 0 && selectedInstanceIds.size === state.instances.length;
    }

    function toggleSelectAllInstances(evt) {
      if (evt.target.checked) {
        state.instances.forEach(item => selectedInstanceIds.add(item.instance_id));
      } else {
        selectedInstanceIds.clear();
      }
      renderManagedInstances();
    }

    async function batchAction(action) {
      if (selectedInstanceIds.size === 0) { instanceActionResultEl.textContent = "请先选择实例。"; return; }
      instanceActionResultEl.textContent = "正在执行...";
      try {
        const result = await fetchJson("/instances/batch-action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, instance_ids: Array.from(selectedInstanceIds) }),
        });
        const ok = result.results.filter(r => r.accepted).length;
        const fail = result.results.filter(r => !r.accepted).length;
        instanceActionResultEl.textContent = `${action} 完成: ${ok} 成功, ${fail} 失败`;
        await loadSummaryStats();
      } catch (error) {
        instanceActionResultEl.textContent = `${action} 失败: ${error.message}`;
      }
    }

    // -- ammo inventory --
    const ammoTabs = document.querySelectorAll("#ammo-inventory-list").length ? [] : [];
    // Re-query since the tabs are inside the same panel
    let currentAmmoTab = "all";
    document.querySelectorAll(".tabs button").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tabs button").forEach(b => b.classList.remove("active-tab"));
        btn.classList.add("active-tab");
        currentAmmoTab = btn.dataset.tab;
        filterAmmoInventory();
      });
    });

    async function loadAmmoInventory() {
      try {
        const data = await fetchJson("/plugin/ammo");
        state.ammoItems = data.items || [];
        filterAmmoInventory();
        const summary = data.summary || {};
        ammoInventorySummaryEl.textContent = `总计: ${summary.total || state.ammoItems.length} | 可用: ${summary.available || 0} | 已分配: ${summary.assigned || 0} | 已消耗: ${summary.consumed || 0}`;
      } catch (error) {
        ammoInventorySummaryEl.textContent = "加载失败: " + error.message;
      }
    }

    function filterAmmoInventory() {
      let filtered = state.ammoItems;
      if (currentAmmoTab !== "all") filtered = filtered.filter(item => (item.status || "") === currentAmmoTab);
      ammoInventoryListEl.innerHTML = "";
      if (!filtered.length) { ammoInventoryListEl.innerHTML = '<div class="empty">没有匹配的弹药。</div>'; return; }
      for (const item of filtered.slice(0, 40)) {
        const div = document.createElement("div");
        div.className = "bl-item";
        div.innerHTML = `<div><span class="bl-target">${escapeHtml(item.target_id)}</span> <span class="meta">${escapeHtml(item.target_value || "")}</span></div>
                         <div><span class="badge">${escapeHtml(item.status || "-")}</span></div>`;
        ammoInventoryListEl.appendChild(div);
      }
    }

    // -- blacklist --
    async function loadBlacklist() {
      try {
        const data = await fetchJson("/blacklist");
        state.blacklist = data.items || [];
        renderBlacklist();
        loadSummaryStats();
      } catch (error) {
        blActionResultEl.textContent = "加载失败: " + error.message;
      }
    }

    function renderBlacklist() {
      blacklistListEl.innerHTML = "";
      if (!state.blacklist.length) { blacklistListEl.innerHTML = '<div class="empty">黑名单为空。</div>'; return; }
      for (const item of state.blacklist) {
        const div = document.createElement("div");
        div.className = "bl-item";
        div.innerHTML = `<div><span class="bl-target">${escapeHtml(item.target_value)}</span> <span class="bl-reason">${escapeHtml(item.reason || "")}</span></div>
                         <button class="danger small" data-target-id="${escapeHtml(item.target_id)}">删除</button>`;
        div.querySelector("button").addEventListener("click", () => removeBlacklistItem(item.target_id));
        blacklistListEl.appendChild(div);
      }
    }

    async function addBlacklistItem() {
      const targetValue = document.getElementById("bl-target-input").value.trim();
      const reason = document.getElementById("bl-reason-input").value.trim();
      if (!targetValue) { blActionResultEl.textContent = "请输入目标值。"; return; }
      blActionResultEl.textContent = "添加中...";
      try {
        await fetchJson("/blacklist/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_value: targetValue, target_type: "handle", reason: reason || null, source: "web-console" }),
        });
        document.getElementById("bl-target-input").value = "";
        document.getElementById("bl-reason-input").value = "";
        blActionResultEl.textContent = "已添加: " + targetValue;
        await loadBlacklist();
      } catch (error) {
        blActionResultEl.textContent = "添加失败: " + error.message;
      }
    }

    async function removeBlacklistItem(targetId) {
      blActionResultEl.textContent = "删除中...";
      try {
        await fetchJson("/blacklist/remove", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_id: targetId }),
        });
        blActionResultEl.textContent = "已删除。";
        await loadBlacklist();
      } catch (error) {
        blActionResultEl.textContent = "删除失败: " + error.message;
      }
    }

    // -- daily stats --
    async function loadDailyStats() {
      const statDate = document.getElementById("daily-stats-date").value;
      if (!statDate) { dailyStatsResultEl.textContent = "请选择日期。"; return; }
      dailyStatsResultEl.textContent = "查询中...";
      try {
        const data = await fetchJson(`/plugin/stats/daily?stat_date=${encodeURIComponent(statDate)}`);
        state.dailyStats = data.items || [];
        renderDailyStats();
        dailyStatsResultEl.textContent = `共 ${state.dailyStats.length} 条记录`;
      } catch (error) {
        dailyStatsResultEl.textContent = "查询失败: " + error.message;
      }
    }

    function renderDailyStats() {
      if (!state.dailyStats.length) {
        dailyStatsTableEl.querySelector("tbody").innerHTML = '<tr><td colspan="7" class="empty">该日期无数据。</td></tr>';
        return;
      }
      dailyStatsTableEl.querySelector("tbody").innerHTML = state.dailyStats.map(item => {
        return `<tr>
          <td>${escapeHtml(item.stat_date || "")}</td>
          <td>${escapeHtml(item.account_id || "-")}</td>
          <td>${escapeHtml(item.script_name || "-")}</td>
          <td>${escapeHtml(item.action_type || "-")}</td>
          <td>${item.success_count}</td>
          <td>${item.failure_count}</td>
          <td>${item.total_count}</td>
        </tr>`;
      }).join("");
    }

    async function cleanupDailyStats() {
      dailyStatsResultEl.textContent = "清理中...";
      try {
        const data = await fetchJson("/plugin/stats/cleanup", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        dailyStatsResultEl.textContent = `已清理 ${data.removed} 条过期记录`;
      } catch (error) {
        dailyStatsResultEl.textContent = "清理失败: " + error.message;
      }
    }

    // -- tasks --
    async function loadTasks() {
      const terminalId = document.getElementById("filter-task-terminal").value.trim();
      const status = document.getElementById("filter-task-status").value;
      const waitReason = document.getElementById("filter-task-wait-reason").value;
      const blockedInstanceId = document.getElementById("filter-task-blocked-instance").value.trim();
      const params = new URLSearchParams();
      if (terminalId) params.set("terminal_id", terminalId);
      if (status) params.set("status", status);
      if (waitReason) params.set("wait_reason", waitReason);
      if (blockedInstanceId) params.set("blocked_by_instance_id", blockedInstanceId);
      const path = params.size ? `/tasks?${params.toString()}` : "/tasks";
      const data = await fetchJson(path);
      renderTaskList(data.items);
      await loadSummaryStats();
    }

    function renderTaskList(items) {
      taskListEl.innerHTML = "";
      if (!items.length) { taskListEl.innerHTML = '<div class="empty">没有匹配的任务。</div>'; return; }
      for (const item of items) {
        const card = document.createElement("button");
        card.className = `card${state.selectedTaskId === item.task_id ? " active" : ""}`;
        card.addEventListener("click", () => selectTask(item.task_id));
        card.innerHTML = `<div class="card-header">
          <div><div class="title">${escapeHtml(item.task_id)}</div><div class="meta">${escapeHtml(item.script_name)} / ${escapeHtml(item.terminal_id)}</div></div>
          <div class="badge ${item.final ? "warn" : "ok"}">${escapeHtml(item.status)}</div></div>
          <div class="badge-row">
            <span class="badge">attempt ${item.attempt_count}/${item.retry_limit + 1}</span>
            <span class="badge ${item.retryable ? "ok" : ""}">retryable=${item.retryable}</span>
            <span class="badge ${item.final ? "warn" : ""}">final=${item.final}</span>
            <span class="badge">${escapeHtml(item.last_error_code || "-")}</span>
            <span class="badge">${escapeHtml(item.parameters?.wait_reason || "-")}</span>
          </div>`;
        taskListEl.appendChild(card);
      }
    }

    async function selectTask(taskId) {
      state.selectedTaskId = taskId;
      actionResultEl.textContent = "未执行动作";
      const task = await fetchJson(`/task/${encodeURIComponent(taskId)}`);
      renderTaskDetails(task);
      taskLogsEl.textContent = "正在加载日志...";
      const logs = await fetchJson(`/logs?task_id=${encodeURIComponent(taskId)}`);
      taskLogsEl.textContent = JSON.stringify(logs.items, null, 2);
      cancelButtonEl.disabled = !task.task_id;
      retryButtonEl.disabled = !task.task_id;
      await selectTerminal(task.terminal_id);
      await loadTasks();
    }

    function renderTaskDetails(task) {
      const params = task.parameters || {};
      const summaryItems = [["任务 ID", task.task_id], ["状态", task.status], ["脚本", task.script_name], ["终端", task.terminal_id],
        ["实例", task.instance_id || "-"], ["尝试次数", `${task.attempt_count}/${task.retry_limit + 1}`],
        ["可重试", String(task.retryable)], ["最终态", String(task.final)], ["等待原因", params.wait_reason || "-"], ["阻塞实例", params.blocked_by_instance_id || "-"]];
      const diagItems = [["错误码", task.last_error_code || "-"], ["错误信息", task.last_error_message || "-"],
        ["结果摘要", params.result_summary || "-"], ["重试阻塞原因", params.retry_blocked_reason || "-"], ["取消阻塞原因", params.cancel_blocked_reason || "-"],
        ["重试已接受", stringifyBool(params.retry_request_accepted)], ["取消已接受", stringifyBool(params.cancel_request_accepted)],
        ["最近运行 ID", params.result_run_id || params.run_id || "-"], ["重试可用时间", params.retry_available_at || "-"]];
      taskSummaryGridEl.innerHTML = summaryItems.map(renderKv).join("");
      taskDiagnosticsGridEl.innerHTML = diagItems.map(renderKv).join("");
      taskResultDetailsEl.textContent = JSON.stringify(params.result_details || {}, null, 2);
      taskDetailEl.textContent = JSON.stringify(task, null, 2);
    }

    async function cancelSelectedTask() {
      if (!state.selectedTaskId) return;
      cancelButtonEl.disabled = true; retryButtonEl.disabled = true; actionResultEl.textContent = "正在取消...";
      try {
        const updated = await fetchJson("/tasks/cancel", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_id: state.selectedTaskId, requested_by: "web-console" }) });
        actionResultEl.textContent = `已取消: ${updated.status}`;
        renderTaskDetails(updated); await loadTasks();
      } catch (error) { actionResultEl.textContent = `失败: ${error.message}`; }
      finally { cancelButtonEl.disabled = false; retryButtonEl.disabled = false; }
    }

    async function retrySelectedTask() {
      if (!state.selectedTaskId) return;
      retryButtonEl.disabled = true; actionResultEl.textContent = "正在提交...";
      try {
        const updated = await fetchJson("/tasks/retry", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_id: state.selectedTaskId, requested_by: "web-console" }) });
        actionResultEl.textContent = `已更新: ${updated.status}`;
        renderTaskDetails(updated);
        const logs = await fetchJson(`/logs?task_id=${encodeURIComponent(state.selectedTaskId)}`);
        taskLogsEl.textContent = JSON.stringify(logs.items, null, 2);
        await loadTasks();
      } catch (error) { actionResultEl.textContent = `失败: ${error.message}`; }
      finally { retryButtonEl.disabled = false; }
    }

    // -- terminals --
    async function loadTerminals() {
      const operatorName = document.getElementById("filter-terminal-operator").value.trim();
      const status = document.getElementById("filter-terminal-status").value;
      const maxParallelTasks = document.getElementById("filter-terminal-max-parallel").value.trim();
      const params = new URLSearchParams();
      if (operatorName) params.set("operator_name", operatorName);
      if (status) params.set("status", status);
      if (maxParallelTasks) params.set("max_parallel_tasks", maxParallelTasks);
      const path = params.size ? `/terminals?${params.toString()}` : "/terminals";
      const data = await fetchJson(path);
      renderTerminalList(data.items);
      await loadSummaryStats();
    }

    function renderTerminalList(items) {
      terminalListEl.innerHTML = "";
      if (!items.length) { terminalListEl.innerHTML = '<div class="empty">没有匹配的终端。</div>'; return; }
      for (const item of items) {
        const card = document.createElement("button");
        card.className = `card${state.selectedTerminalId === item.terminal_id ? " active" : ""}`;
        card.addEventListener("click", () => selectTerminal(item.terminal_id));
        card.innerHTML = `<div class="card-header">
          <div><div class="title">${escapeHtml(item.terminal_id)}</div><div class="meta">${escapeHtml(item.hostname)} / ${escapeHtml(item.operator_name)}</div></div>
          <div class="badge ok">${escapeHtml(item.status)}</div></div>
          <div class="badge-row">
            <span class="badge">instances=${item.metadata?.active_instance_count ?? 0}</span>
            <span class="badge">active=${item.metadata?.active_task_count ?? 0}</span>
            <span class="badge">queued=${item.metadata?.queued_task_count ?? 0}</span>
            <span class="badge">max=${item.metadata?.max_parallel_tasks ?? "-"}</span>
            <span class="badge">${escapeHtml(item.agent_version || "-")}</span>
          </div>`;
        terminalListEl.appendChild(card);
      }
    }

    async function selectTerminal(terminalId) {
      state.selectedTerminalId = terminalId;
      const terminal = await fetchJson(`/terminal/${encodeURIComponent(terminalId)}`);
      terminalDetailEl.textContent = JSON.stringify(terminal, null, 2);
      terminalInstancesEl.textContent = "正在加载实例...";
      const instances = await fetchJson(`/instances?terminal_id=${encodeURIComponent(terminalId)}`);
      terminalInstancesEl.textContent = JSON.stringify(instances.items, null, 2);
      await loadTerminals();
    }

    function renderScriptStatus() {
      const followTasks = state.tasks.filter(t => t.script_name === "follow" && ["queued", "dispatched", "running"].includes(t.status));
      const chatTasks = state.tasks.filter(t => t.script_name === "chat" && ["queued", "dispatched", "running"].includes(t.status));
      const followAccounts = (state.accounts || []).filter(a => (a.capability_tags || []).includes("follow"));
      const chatAccounts = (state.accounts || []).filter(a => (a.capability_tags || []).includes("chat"));
      const fb = document.getElementById("follow-status-badge");
      fb.textContent = followAccounts.length > 0 ? "已配置" : "未配置";
      fb.className = "badge " + (followAccounts.length > 0 ? "ok" : "warn");
      document.getElementById("follow-run-detail").textContent = followAccounts.length + " 个账号、" + followTasks.length + " 个执行中任务";
      const cb = document.getElementById("chat-status-badge");
      cb.textContent = chatAccounts.length > 0 ? "已配置" : "未配置";
      cb.className = "badge " + (chatAccounts.length > 0 ? "ok" : "warn");
      document.getElementById("chat-run-detail").textContent = chatAccounts.length + " 个账号、" + chatTasks.length + " 个执行中任务";
    }

    // -- ammo submit (keep existing) --
    async function submitAmmo() {
      ammoResultEl.textContent = "添加弹药...";
      try {
        const scriptLane = document.getElementById("ammo-script-lane").value;
        const targetInput = document.getElementById("ammo-target-input").value.trim();
        const creatorInput = document.getElementById("ammo-creator-id").value.trim();
        if (!targetInput) throw new Error("请输入目标 @handle 或链接");
        const handle = targetInput.replace(/^@/, "").trim().toLowerCase();
        const creatorId = creatorInput || handle || "manual";
        const source = scriptLane === "chat" ? "content_chat.js" : "content_follow.js";
        const response = await fetchJson("/plugin/ammo/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_value: handle || targetInput, target_type: "handle", source: source, creator_id: creatorId }),
        });
        ammoResultEl.textContent = "已添加: " + response.target_id + " (" + response.target_value + ")";
        document.getElementById("ammo-target-input").value = "";
        document.getElementById("ammo-creator-id").value = "";
        await loadSummaryStats(); await loadAmmoInventory();
      } catch (error) { ammoResultEl.textContent = "添加失败: " + error.message; }
    }

    // -- init --
    loadSummaryStats();
    Promise.all([loadTasks(), loadTerminals(), loadBlacklist(), loadAmmoInventory()]).catch(error => {
      taskListEl.innerHTML = `<div class="empty">加载失败: ${escapeHtml(error.message)}</div>`;
    });
  </script>
</body>
</html>"""
