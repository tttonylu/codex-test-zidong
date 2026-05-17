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
      --shadow: 0 12px 32px rgba(25, 37, 44, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(215,111,48,0.14), transparent 30%),
        radial-gradient(circle at left center, rgba(13,107,102,0.12), transparent 25%),
        var(--bg);
    }
    .page {
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }
    .hero {
      display: grid;
      gap: 14px;
      margin-bottom: 20px;
    }
    .hero h1 {
      margin: 0;
      font-size: 34px;
      line-height: 1.1;
      letter-spacing: -0.03em;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      max-width: 900px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }
    .stat, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: var(--shadow);
    }
    .stat {
      padding: 16px 18px;
    }
    .stat .label {
      color: var(--muted);
      font-size: 13px;
    }
    .stat .value {
      font-size: 28px;
      margin-top: 6px;
      font-weight: 700;
    }
    .layout {
      display: grid;
      grid-template-columns: 1.2fr 1.1fr;
      gap: 18px;
    }
    .column {
      display: grid;
      gap: 18px;
      align-content: start;
    }
    .panel {
      padding: 16px;
    }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 18px;
    }
    .panel h3 {
      margin: 0 0 10px;
      font-size: 15px;
    }
    .toolbar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 12px;
      align-items: center;
    }
    input, select, button {
      border-radius: 12px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      font: inherit;
      background: white;
    }
    input, select {
      min-width: 140px;
    }
    button {
      cursor: pointer;
      background: var(--brand);
      color: white;
      border-color: var(--brand);
    }
    button.secondary {
      background: var(--panel-2);
      color: var(--ink);
      border-color: var(--line);
    }
    button.warn {
      background: var(--brand-2);
      border-color: var(--brand-2);
    }
    button.card {
      color: inherit;
      text-align: left;
      width: 100%;
    }
    .list {
      display: grid;
      gap: 10px;
      max-height: 520px;
      overflow: auto;
      padding-right: 4px;
    }
    .card {
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(247,241,228,0.95));
      border-radius: 16px;
      padding: 14px;
      display: grid;
      gap: 8px;
    }
    .card.active {
      border-color: var(--brand);
      box-shadow: inset 0 0 0 1px rgba(13,107,102,0.18);
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }
    .title {
      font-weight: 700;
      font-size: 15px;
      word-break: break-word;
    }
    .meta {
      color: var(--muted);
      font-size: 12px;
    }
    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      border: 1px solid var(--line);
      background: white;
    }
    .badge.ok { color: var(--ok); border-color: rgba(44,110,73,0.24); }
    .badge.warn { color: var(--warn); border-color: rgba(177,70,35,0.24); }
    .detail-stack {
      display: grid;
      gap: 12px;
    }
    .detail-section {
      display: grid;
      gap: 8px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.7);
    }
    .kv-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .kv {
      display: grid;
      gap: 4px;
      padding: 10px;
      border-radius: 12px;
      background: var(--panel-3);
    }
    .kv .k {
      color: var(--muted);
      font-size: 12px;
    }
    .kv .v {
      font-size: 14px;
      word-break: break-word;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      max-height: 260px;
      overflow: auto;
    }
    .muted { color: var(--muted); }
    .empty {
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 14px;
      padding: 18px;
      text-align: center;
      background: rgba(255,255,255,0.55);
    }
    @media (max-width: 960px) {
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .layout { grid-template-columns: 1fr; }
      .kv-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 640px) {
      .stats { grid-template-columns: 1fr; }
      .hero h1 { font-size: 28px; }
    }
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>NAS Web Console</h1>
      <p>当前页面已经进入最小运营面阶段。这里直接展示任务、终端、日志和诊断信息，用来快速判断某个任务是否失败、能不能重试、为什么被阻塞。</p>
    </section>

    <section class="stats">
      <div class="stat"><div class="label">终端数</div><div class="value" id="stat-terminals">-</div></div>
      <div class="stat"><div class="label">实例数</div><div class="value" id="stat-instances">-</div></div>
      <div class="stat"><div class="label">任务数</div><div class="value" id="stat-tasks">-</div></div>
      <div class="stat"><div class="label">可重试任务</div><div class="value" id="stat-retryable">-</div></div>
    </section>

    <section class="layout">
      <div class="column">
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
              <option value="failed">failed</option>
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

      <div class="column">
        <div class="panel">
          <h2>任务详情</h2>
          <div class="toolbar">
            <button class="secondary" id="cancel-task" disabled>取消当前任务</button>
            <button class="warn" id="retry-task" disabled>重试当前任务</button>
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

        <div class="panel">
          <h2>终端摘要</h2>
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
    const state = {
      selectedTaskId: null,
      selectedTerminalId: null,
    };

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

    document.getElementById("reload-tasks").addEventListener("click", () => loadTasks());
    document.getElementById("reload-terminals").addEventListener("click", () => loadTerminals());
    document.getElementById("filter-task-status").addEventListener("change", () => loadTasks());
    document.getElementById("filter-task-wait-reason").addEventListener("change", () => loadTasks());
    document.getElementById("filter-terminal-status").addEventListener("change", () => loadTerminals());
    document.getElementById("filter-task-terminal").addEventListener("keydown", event => {
      if (event.key === "Enter") loadTasks();
    });
    document.getElementById("filter-task-blocked-instance").addEventListener("keydown", event => {
      if (event.key === "Enter") loadTasks();
    });
    document.getElementById("filter-terminal-operator").addEventListener("keydown", event => {
      if (event.key === "Enter") loadTerminals();
    });
    document.getElementById("filter-terminal-max-parallel").addEventListener("keydown", event => {
      if (event.key === "Enter") loadTerminals();
    });
    cancelButtonEl.addEventListener("click", cancelSelectedTask);
    retryButtonEl.addEventListener("click", retrySelectedTask);

    async function fetchJson(path, options) {
      const response = await fetch(path, options);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "request failed");
      }
      return data;
    }

    async function loadSummaryStats() {
      const [terminals, instances, tasks] = await Promise.all([
        fetchJson("/terminals"),
        fetchJson("/instances"),
        fetchJson("/tasks"),
      ]);
      document.getElementById("stat-terminals").textContent = terminals.items.length;
      document.getElementById("stat-instances").textContent = instances.items.length;
      document.getElementById("stat-tasks").textContent = tasks.items.length;
      document.getElementById("stat-retryable").textContent = tasks.items.filter(item => item.retryable).length;
    }

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
      if (!items.length) {
        taskListEl.innerHTML = '<div class="empty">没有匹配的任务。</div>';
        return;
      }
      for (const item of items) {
        const card = document.createElement("button");
        card.className = `card${state.selectedTaskId === item.task_id ? " active" : ""}`;
        card.addEventListener("click", () => selectTask(item.task_id));
        card.innerHTML = `
          <div class="card-header">
            <div>
              <div class="title">${escapeHtml(item.task_id)}</div>
              <div class="meta">${escapeHtml(item.script_name)} / ${escapeHtml(item.terminal_id)}</div>
            </div>
            <div class="badge ${item.final ? "warn" : "ok"}">${escapeHtml(item.status)}</div>
          </div>
          <div class="badge-row">
            <span class="badge">attempt ${item.attempt_count}/${item.retry_limit + 1}</span>
            <span class="badge ${item.retryable ? "ok" : ""}">retryable=${item.retryable}</span>
            <span class="badge ${item.final ? "warn" : ""}">final=${item.final}</span>
            <span class="badge">${escapeHtml(item.last_error_code || "-")}</span>
            <span class="badge">${escapeHtml(item.parameters?.wait_reason || "-")}</span>
          </div>
        `;
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
      const summaryItems = [
        ["任务 ID", task.task_id],
        ["状态", task.status],
        ["脚本", task.script_name],
        ["终端", task.terminal_id],
        ["实例", task.instance_id || "-"],
        ["尝试次数", `${task.attempt_count}/${task.retry_limit + 1}`],
        ["可重试", String(task.retryable)],
        ["最终态", String(task.final)],
        ["等待原因", params.wait_reason || "-"],
        ["阻塞实例", params.blocked_by_instance_id || "-"],
      ];
      const diagnosticsItems = [
        ["错误码", task.last_error_code || "-"],
        ["错误信息", task.last_error_message || "-"],
        ["结果摘要", params.result_summary || "-"],
        ["重试阻塞原因", params.retry_blocked_reason || "-"],
        ["取消阻塞原因", params.cancel_blocked_reason || "-"],
        ["重试已接受", stringifyBool(params.retry_request_accepted)],
        ["取消已接受", stringifyBool(params.cancel_request_accepted)],
        ["最近运行 ID", params.result_run_id || params.run_id || "-"],
        ["重试可用时间", params.retry_available_at || "-"],
      ];
      taskSummaryGridEl.innerHTML = summaryItems.map(renderKv).join("");
      taskDiagnosticsGridEl.innerHTML = diagnosticsItems.map(renderKv).join("");
      taskResultDetailsEl.textContent = JSON.stringify(params.result_details || {}, null, 2);
      taskDetailEl.textContent = JSON.stringify(task, null, 2);
    }

    async function cancelSelectedTask() {
      if (!state.selectedTaskId) return;
      cancelButtonEl.disabled = true;
      retryButtonEl.disabled = true;
      actionResultEl.textContent = "正在取消...";
      try {
        const updated = await fetchJson("/tasks/cancel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: state.selectedTaskId, requested_by: "web-console" }),
        });
        actionResultEl.textContent = `已取消: ${updated.status}`;
        renderTaskDetails(updated);
        await loadTasks();
      } catch (error) {
        actionResultEl.textContent = `失败: ${error.message}`;
      } finally {
        cancelButtonEl.disabled = false;
        retryButtonEl.disabled = false;
      }
    }

    async function retrySelectedTask() {
      if (!state.selectedTaskId) return;
      retryButtonEl.disabled = true;
      actionResultEl.textContent = "正在提交...";
      try {
        const updated = await fetchJson("/tasks/retry", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: state.selectedTaskId, requested_by: "web-console" }),
        });
        actionResultEl.textContent = `已更新: ${updated.status}`;
        renderTaskDetails(updated);
        const logs = await fetchJson(`/logs?task_id=${encodeURIComponent(state.selectedTaskId)}`);
        taskLogsEl.textContent = JSON.stringify(logs.items, null, 2);
        await loadTasks();
      } catch (error) {
        actionResultEl.textContent = `失败: ${error.message}`;
      } finally {
        retryButtonEl.disabled = false;
      }
    }

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
      if (!items.length) {
        terminalListEl.innerHTML = '<div class="empty">没有匹配的终端。</div>';
        return;
      }
      for (const item of items) {
        const card = document.createElement("button");
        card.className = `card${state.selectedTerminalId === item.terminal_id ? " active" : ""}`;
        card.addEventListener("click", () => selectTerminal(item.terminal_id));
        card.innerHTML = `
          <div class="card-header">
            <div>
              <div class="title">${escapeHtml(item.terminal_id)}</div>
              <div class="meta">${escapeHtml(item.hostname)} / ${escapeHtml(item.operator_name)}</div>
            </div>
            <div class="badge ok">${escapeHtml(item.status)}</div>
          </div>
          <div class="badge-row">
            <span class="badge">instances=${item.metadata?.active_instance_count ?? 0}</span>
            <span class="badge">active=${item.metadata?.active_task_count ?? 0}</span>
            <span class="badge">queued=${item.metadata?.queued_task_count ?? 0}</span>
            <span class="badge">max=${item.metadata?.max_parallel_tasks ?? "-"}</span>
            <span class="badge">${escapeHtml(item.agent_version || "-")}</span>
          </div>
        `;
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

    function renderKv([key, value]) {
      return `<div class="kv"><div class="k">${escapeHtml(key)}</div><div class="v">${escapeHtml(value ?? "-")}</div></div>`;
    }

    function stringifyBool(value) {
      if (value === true) return "true";
      if (value === false) return "false";
      return "-";
    }

    function escapeHtml(text) {
      return String(text)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    Promise.all([loadTasks(), loadTerminals()]).catch(error => {
      const message = `<div class="empty">加载失败: ${escapeHtml(error.message)}</div>`;
      taskListEl.innerHTML = message;
      terminalListEl.innerHTML = message;
    });
  </script>
</body>
</html>"""
