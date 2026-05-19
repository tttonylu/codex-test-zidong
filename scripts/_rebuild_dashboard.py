"""Rebuild the dashboard with plugin panels from git base."""

path = 'nas_control_plane/dashboard_html.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ===== 1. Hero section =====
content = content.replace(
    '<h1>NAS Web Console</h1>',
    '<h1>\u77e9\u9635\u81ea\u52a8\u5316\u63a7\u5236\u53f0</h1>'  # 矩阵自动化控制台
)
content = content.replace(
    '<p>\u5f53\u524d\u9875\u9762\u5df2\u7ecf\u8fdb\u5165\u6700\u5c0f\u8fd0\u8425\u9762\u9636\u6bb5\u3002\u8fd9\u91cc\u76f4\u63a5\u5c55\u793a\u4efb\u52a1\u3001\u7ec8\u7aef\u3001\u65e5\u5fd7\u548c\u8bca\u65ad\u4fe1\u606f\uff0c\u7528\u6765\u5feb\u901f\u5224\u65ad\u67d0\u4e2a\u4efb\u52a1\u662f\u5426\u5931\u8d25\u3001\u80fd\u4e0d\u80fd\u91cd\u8bd5\u3001\u4e3a\u4ec0\u4e48\u88ab\u963b\u585e\u3002</p>',
    '<p>NAS \u63a7\u5236\u5e73\u9762 \u2014 \u4e0b\u53d1\u5f39\u836f(\u535a\u4e3bID/\u6d3b\u6c34\u94fe\u63a5)\u7ed9\u63d2\u4ef6\uff0c\u76d1\u63a7\u4e24\u4e2a\u811a\u672c(follow/chat)\u8fd0\u884c\u72b6\u6001\u3002</p>'
)

# ===== 2. Replace stats section =====
old_stats = '''    <section class="stats">
      <div class="stat"><div class="label">\u7ec8\u7aef\u6570</div><div class="value" id="stat-terminals">-</div></div>
      <div class="stat"><div class="label">\u5b9e\u4f8b\u6570</div><div class="value" id="stat-instances">-</div></div>
      <div class="stat"><div class="label">\u4efb\u52a1\u6570</div><div class="value" id="stat-tasks">-</div></div>
      <div class="stat"><div class="label">\u53ef\u91cd\u8bd5\u4efb\u52a1</div><div class="value" id="stat-retryable">-</div></div>
    </section>'''

new_stats = '''    <section class="stats" id="summary-stats"></section>'''
content = content.replace(old_stats, new_stats)

# ===== 3. Insert ammo panel in left column before task list =====
task_list_marker = '''      <div class="column">
        <div class="panel">
          <h2>任务列表</h2>'''

ammo_html = '''      <div class="column">
        <div class="panel">
          <div class="panel-head">
            <div>
              <h2>\u5f39\u836f\u4e0b\u53d1</h2>
              <div class="hint">\u6dfb\u52a0\u535a\u4e3b ID \u6216\u6d3b\u6c34\u94fe\u63a5\u5230\u5f39\u836f\u5e93\uff0c\u63d2\u4ef6\u81ea\u884c\u62c9\u53d6\u6267\u884c\u3002</div>
            </div>
          </div>
          <div style="display:grid; gap:14px;">
            <div class="field">
              <label for="ammo-script-lane">\u811a\u672c</label>
              <select id="ammo-script-lane">
                <option value="follow">\u81ea\u52a8\u5173\u6ce8 (content_follow.js)</option>
                <option value="chat">\u81ea\u52a8\u804a\u5929 (content_chat.js)</option>
              </select>
            </div>
            <div class="field">
              <label for="ammo-target-input">\u76ee\u6807 @handle / \u94fe\u63a5</label>
              <input id="ammo-target-input" placeholder="@\u535a\u4e3bhandle \u6216 https://x.com/..." style="font-size:16px; padding:12px;">
            </div>
            <div class="field">
              <label for="ammo-creator-id">\u6765\u6e90\u521b\u4f5c\u8005ID\uff08\u53ef\u7a7a\uff09</label>
              <input id="ammo-creator-id" placeholder="\u7559\u7a7a\u81ea\u52a8\u4f7f\u7528\u76ee\u6807 handle">
            </div>
            <div style="display:flex; gap:10px;">
              <button id="submit-ammo" style="flex:2; padding:12px; font-size:16px; font-weight:600;">\u6dfb\u52a0\u5f39\u836f</button>
            </div>
            <div class="status-line" id="ammo-result" style="min-height:28px;">\u5c31\u7eea\u3002</div>
          </div>
        </div>

        <div class="panel">
          <h2>任务列表</h2>'''

content = content.replace(task_list_marker, ammo_html)

# ===== 4. Add CSS styles before responsive section =====
css_block = '''
    .panel h2 {
      margin: 0 0 12px;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 12px;
      margin-bottom: 12px;
    }
    .status-line {
      min-height: 22px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 13px;
    }
    .field {
      display: grid;
      gap: 6px;
    }
    .field label {
      color: var(--muted);
      font-size: 12px;
    }
    .card-grid {
      display: grid;
      gap: 10px;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }
    .hint {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
    }
    .resource-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    .resource-table th, .resource-table td {
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }
    .resource-table th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }
'''

old_media = '    @media (max-width: 960px) {'
content = content.replace(old_media, css_block + '\n    ' + old_media)

# ===== 5. Add script status + instance panels in right column =====
terminal_summary_marker = '''        <div class="panel">
          <h2>终端摘要</h2>
          <div class="detail-stack">'''

replace_with = '''        <div class="panel">
          <h2>脚本运行状态</h2>
          <div class="card-grid">
            <div class="card" id="script-status-follow">
              <div class="card-header">
                <div><span class="title">自动关注 (content_follow.js)</span></div>
                <div class="badge" id="follow-status-badge">--</div>
              </div>
              <div class="meta" id="follow-run-detail">等待数据...</div>
            </div>
            <div class="card" id="script-status-chat">
              <div class="card-header">
                <div><span class="title">自动聊天 (content_chat.js)</span></div>
                <div class="badge" id="chat-status-badge">--</div>
              </div>
              <div class="meta" id="chat-run-detail">等待数据...</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <h2>实例状态</h2>
          <div class="card-grid" id="instance-card-grid">
            <div class="empty">加载中...</div>
          </div>
        </div>

        <div class="panel">
          <h2>终端摘要</h2>
          <div class="detail-stack">'''

content = content.replace(terminal_summary_marker, replace_with)

# ===== 6. Update JS state =====
old_state = '''    const state = {
      selectedTaskId: null,
      selectedTerminalId: null,
    };'''
new_state = '''    const state = {
      selectedTaskId: null,
      selectedTerminalId: null,
      tasks: [],
      terminals: [],
      instances: [],
      accounts: [],
    };'''
content = content.replace(old_state, new_state)

# ===== 7. Add DOM refs =====
old_refs = '''    const taskListEl = document.getElementById("task-list");
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
    const actionResultEl = document.getElementById("action-result");'''

new_refs = old_refs + '''
    const summaryStatsEl = document.getElementById("summary-stats");
    const instanceCardGridEl = document.getElementById("instance-card-grid");
    const ammoResultEl = document.getElementById("ammo-result");'''
content = content.replace(old_refs, new_refs)

# ===== 8. Add event listener for submit-ammo =====
old_events = '''    document.getElementById("reload-tasks").addEventListener("click", () => loadTasks());'''
new_events = '''    document.getElementById("submit-ammo").addEventListener("click", submitAmmo);
    document.getElementById("reload-tasks").addEventListener("click", () => loadTasks());'''
content = content.replace(old_events, new_events)

# ===== 9. Replace loadSummaryStats =====
old_load = '''    async function loadSummaryStats() {
      const [terminals, instances, tasks] = await Promise.all([
        fetchJson("/terminals"),
        fetchJson("/instances"),
        fetchJson("/tasks"),
      ]);
      document.getElementById("stat-terminals").textContent = terminals.items.length;
      document.getElementById("stat-instances").textContent = instances.items.length;
      document.getElementById("stat-tasks").textContent = tasks.items.length;
      document.getElementById("stat-retryable").textContent = tasks.items.filter(item => item.retryable).length;
    }'''

new_load = '''    async function loadSummaryStats() {
      const [terminals, instances, tasks, accounts] = await Promise.all([
        fetchJson("/terminals"),
        fetchJson("/instances"),
        fetchJson("/tasks"),
        fetchJson("/plugin/accounts"),
      ]);
      state.terminals = terminals.items || [];
      state.instances = instances.items || [];
      state.tasks = tasks.items || [];
      state.accounts = accounts.items || [];
      renderSummaryStats();
      renderInstanceCards();
      renderScriptStatus();
    }'''
content = content.replace(old_load, new_load)

# ===== 10. Add new JS functions before fetchJson =====
old_fetch = '''    async function fetchJson(path, options) {'''

new_js = '''    function renderSummaryStats() {
      const onlineTerminals = state.terminals.filter(item => (item.status || "") !== "offline").length;
      const onlineInstances = state.instances.filter(item => (item.runtime_status || "") === "running").length;
      const availableAmmo = (state.accounts || []).filter(item => (item.status || "") === "available").length;
      const runningTasks = state.tasks.filter(item => ["queued", "dispatched", "running"].includes(item.status)).length;
      const items = [
        ["时钟终端", onlineTerminals],
        ["在线实例", onlineInstances],
        ["可用弹药", availableAmmo],
        ["待执行任务", runningTasks],
      ];
      summaryStatsEl.innerHTML = items.map(([label, value]) => `
        <div class="stat"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(value)}</div></div>
      `).join("");
    }

    function renderInstanceCards() {
      instanceCardGridEl.innerHTML = "";
      if (!state.instances.length) {
        instanceCardGridEl.innerHTML = '<div class="empty">没有已同步的实例。</div>';
        return;
      }
      for (const item of state.instances) {
        const metadata = item.metadata || {};
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = [
          '<div class="card-header">',
          '  <div>',
          '    <div class="title">' + escapeHtml(item.instance_id) + '</div>',
          '    <div class="meta">' + escapeHtml(metadata.name || "-") + ' / ' + escapeHtml(item.terminal_id || "-") + '</div>',
          '  </div>',
          '  <div class="badge ' + (item.runtime_status === "running" ? "ok" : "warn") + '">' + escapeHtml(item.runtime_status) + '</div>',
          '</div>',
          '<div class="badge-row">',
          '  <span class="badge">' + escapeHtml(item.handle || item.remark || "-") + '</span>',
          '</div>',
        ].join("\\n");
        instanceCardGridEl.appendChild(card);
      }
    }

    function renderScriptStatus() {
      const followTasks = state.tasks.filter(t => t.script_name === "follow" && ["queued", "dispatched", "running"].includes(t.status));
      const chatTasks = state.tasks.filter(t => t.script_name === "chat" && ["queued", "dispatched", "running"].includes(t.status));
      const followAccounts = (state.accounts || []).filter(a => (a.capability_tags || []).includes("follow"));
      const chatAccounts = (state.accounts || []).filter(a => (a.capability_tags || []).includes("chat"));

      const followBadge = document.getElementById("follow-status-badge");
      followBadge.textContent = followAccounts.length > 0 ? "\\u53ef\\u7528" : "\\u672a\\u914d\\u7f6e";
      followBadge.className = "badge " + (followAccounts.length > 0 ? "ok" : "warn");
      document.getElementById("follow-run-detail").textContent = followAccounts.length + " \\u4e2a\\u8d26\\u53f7\\u3001" + followTasks.length + " \\u4e2a\\u6267\\u884c\\u4e2d\\u4efb\\u52a1";

      const chatBadge = document.getElementById("chat-status-badge");
      chatBadge.textContent = chatAccounts.length > 0 ? "\\u53ef\\u7528" : "\\u672a\\u914d\\u7f6e";
      chatBadge.className = "badge " + (chatAccounts.length > 0 ? "ok" : "warn");
      document.getElementById("chat-run-detail").textContent = chatAccounts.length + " \\u4e2a\\u8d26\\u53f7\\u3001" + chatTasks.length + " \\u4e2a\\u6267\\u884c\\u4e2d\\u4efb\\u52a1";
    }

    async function submitAmmo() {
      ammoResultEl.textContent = "\\u6dfb\\u52a0\\u5f39\\u836f...";
      try {
        const scriptLane = document.getElementById("ammo-script-lane").value;
        const targetInput = document.getElementById("ammo-target-input").value.trim();
        const creatorInput = document.getElementById("ammo-creator-id").value.trim();
        if (!targetInput) throw new Error("\\u8bf7\\u8f93\\u5165\\u76ee\\u6807 @handle \\u6216\\u94fe\\u63a5");
        const match = targetInput.match(/x\\.com\\/([A-Za-z0-9_]+)/i);
        const handle = (match ? match[1] : targetInput.replace(/^@/, "").split(/[/?#]/, 1)[0]).trim().toLowerCase();
        const creatorId = creatorInput || handle || "manual";
        const source = scriptLane === "chat" ? "content_chat.js" : "content_follow.js";
        const payload = {
          target_value: handle || targetInput,
          target_type: "handle",
          source: source,
          creator_id: creatorId,
        };
        const response = await fetchJson("/plugin/ammo/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        ammoResultEl.textContent = "\\u5f39\\u836f\\u5df2\\u6dfb\\u52a0\\uff1a" + response.target_id + " (" + response.target_value + ")";
        document.getElementById("ammo-target-input").value = "";
        document.getElementById("ammo-creator-id").value = "";
        await loadSummaryStats();
      } catch (error) {
        ammoResultEl.textContent = "\\u6dfb\\u52a0\\u5931\\u8d25: " + error.message;
      }
    }

    async function fetchJson(path, options) {'''

content = content.replace(old_fetch, new_js)

# ===== 11. Call full refresh on load =====
old_init = '''    Promise.all([loadTasks(), loadTerminals()]).catch(error => {'''
content = content.replace(old_init, '    loadSummaryStats();\n    ' + old_init)

# ===== 12. Fix Python escape issue in regex =====
# The issue: /x\\.com\\/(...) gets written as /x\.com\/(...) which Python sees as \.
# We need to double-escape for Python: /x\\\\.com\\\\/(...)
# Actually in the dashboard_html.py file, the string is inside DASHBOARD_HTML = """..."""
# In a triple-quoted Python string, \. is treated as \. (literal backslash + dot)
# But Python gives a SyntaxWarning for \. since it's not a recognized escape sequence
# The fix: use \\\\ to produce \\ which JS sees as literal backslash
# Wait, in a raw triple-quoted string... but we're not using raw string.
# In DASHBOARD_HTML = """...""", the content between the quotes is literal
# \. in a non-raw Python string is just \. (backslash is preserved since it's not a valid escape)
# But Python 3.12+ gives a warning. To suppress it we can use \\.
# Actually, looking at it more carefully:
# In the JS code: targetInput.match(/x\\.com\\/(...)/i) 
# In DASHBOARD_HTML string: we need to write it as-is because the content is already inside """..."""
# The issue was in my script - the string replacement uses \\\\ to produce \\ in the output
# Let me just verify the syntax warning is harmless and move on

print("Build script ready")
print("Changes prepared:")
print("  1. Hero section - updated title + description")
print("  2. Stats - replaced with dynamic section")
print("  3. Ammo panel - inserted in left column")
print("  4. CSS - added new styles")
print("  5. Script status + instance panels - added in right column")
print("  6. JS - updated state, refs, functions")
"