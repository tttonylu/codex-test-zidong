// X-Matrix-Bot background bridge
// Version: 11.12.4 (补全引擎命令轮询)
// Purpose: keep only the current NAS -> terminal -> instance -> plugin bridge chain.

const API_TOKEN = "xm2026_a1b2c3d4e5";
const DEFAULT_NAS_URL = "http://192.168.0.100:3210";
const DEFAULT_GUARD_AGENT_URL = "http://127.0.0.1:54346";
const HEARTBEAT_INTERVAL_MINUTES = 0.1;

let guardAgentAvailable = false;

chrome.runtime.onInstalled.addListener(() => {
    function keepSwAlive() {
    // Keep Service Worker event loop busy
    setInterval(() => {
        chrome.storage.local.get(['matrix_keepalive'], () => {});
    }, 20000);
}

keepSwAlive();
setupKeepAlive();
    keepSwAlive();
});

chrome.runtime.onStartup.addListener(() => {
    function keepSwAlive() {
    // Keep Service Worker event loop busy
    setInterval(() => {
        chrome.storage.local.get(['matrix_keepalive'], () => {});
    }, 20000);
}

keepSwAlive();
setupKeepAlive();
    keepSwAlive();
});

function keepSwAlive() {
    // Keep Service Worker event loop busy
    setInterval(() => {
        chrome.storage.local.get(['matrix_keepalive'], () => {});
    }, 20000);
}

keepSwAlive();
setupKeepAlive();

function setupKeepAlive() {
    if (!chrome.alarms) {
        return;
    }
    chrome.alarms.create("matrix_heartbeat", { periodInMinutes: HEARTBEAT_INTERVAL_MINUTES });
}

chrome.alarms.onAlarm.addListener(async alarm => {
    if (alarm.name !== "matrix_heartbeat") {
        return;
    }
    await sendFallbackHeartbeat();
    await pollEngineCommands();
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    handleMessage(request)
        .then(result => sendResponse(result))
        .catch(error => sendResponse({ status: "error", message: error instanceof Error ? error.message : String(error) }));
    return true;
});

async function handleMessage(request) {
    switch (request.action) {
        case "ping":
            return { status: "pong" };
        case "open_options":
            chrome.runtime.openOptionsPage();
            return { status: "success" };
        case "log_action":
        case "chat_log_action":
            return handleActionLog(request.payload || request);
        case "send_report":
            return handleHeartbeat(request.payload || {});
        case "fetch_task":
            return handleTaskPull(request);
        case "guard_current_task":
            return fetchGuardCurrentTask();
        case "guard_task_status":
            return fetchGuardTaskStatus();
        case "guard_next_action":
            return fetchGuardNextAction(request.payload || {});
        case "guard_complete_action":
            return completeGuardAction(request.payload || {});
        case "guard_fail_action":
            return failGuardAction(request.payload || {});
        case "plugin_login_success":
            return handlePluginLoginSuccess(request.payload || {});
        case "plugin_force_name_sync":
            return handleForceNameSync(request.payload || {});
        case "plugin_instance_restart":
            return handleInstanceRestart(request.payload || {});
        case "report_user_id":
            return handleUserIdentity(request);
        case "fetch_links":
            return handleFetchLinks();
        default:
            return { status: "error", message: `unsupported action: ${request.action || "unknown"}` };
    }
}

async function handleActionLog(payload) {
    const response = await postGuard("/ext/action_log", payload);
    return { status: "success", data: response };
}

async function handleHeartbeat(payload) {
    await chrome.storage.local.set({
        matrix_last_heartbeat: payload,
        matrix_last_heartbeat_time: Date.now(),
    });
    if (payload.worker_id) {
        await chrome.storage.local.set({ matrix_worker_id: payload.worker_id });
    }
    const response = await postGuard("/ext/heartbeat", payload);
    return { status: "success", data: response };
}

async function handleTaskPull(request) {
    const payload = {
        terminal_id: request.terminal_id || null,
        instance_id: request.instance_id || request.browser_id || request.bit_id || null,
        account_id: request.account_id || request.profile_id || request.worker_id || null,
        script_name: request.script_name || request.engine || "follow",
        plugin_name: request.plugin_name || "content_follow.js",
    };
    const response = await postGuard("/plugin/task/pull", payload);
    if (response && response.accepted && response.task) {
        const task = response.task;
        await chrome.storage.local.set({
            matrix_current_task: task,
            matrix_current_task_id: task.task_id || null,
            matrix_current_action_plan: Array.isArray(task.action_plan) ? task.action_plan : [],
            matrix_current_target: task.target || {},
            matrix_current_copy_payload: task.copy_payload || null,
        });
        const fallbackCreator =
            (task.target && (task.target.handle || task.target.creator_id || task.target.target_handle)) ||
            (task.parameters && (task.parameters.target_handle || task.parameters.ammo_target_value)) ||
            "EMPTY";
        return { status: "success", data: fallbackCreator, task };
    }
    return { status: "success", data: "EMPTY", task: null };
}

async function fetchGuardCurrentTask() {
    const token = API_TOKEN;
    const response = await fetch(`${getGuardAgentUrl()}/plugin/current-task`, {
        method: "GET",
        headers: {
            "X-API-Token": token,
        },
    });
    const data = await safeJson(response);
    if (!response.ok) {
        throw new Error(data.error || data.message || `guard current-task failed: HTTP ${response.status}`);
    }
    return { status: "success", task: data.task || null };
}

async function fetchGuardTaskStatus() {
    const token = API_TOKEN;
    const response = await fetch(`${getGuardAgentUrl()}/plugin/task/status`, {
        method: "GET",
        headers: {
            "X-API-Token": token,
        },
    });
    const data = await safeJson(response);
    if (!response.ok) {
        throw new Error(data.error || data.message || `guard task-status failed: HTTP ${response.status}`);
    }
    return { status: "success", data };
}

async function fetchGuardNextAction(payload) {
    const data = await postGuard("/plugin/task/next-action", payload || {});
    return { status: "success", data };
}

async function completeGuardAction(payload) {
    const data = await postGuard("/plugin/task/complete-action", payload || {});
    return { status: "success", data };
}

async function failGuardAction(payload) {
    const data = await postGuard("/plugin/task/fail-action", payload || {});
    return { status: "success", data };
}

async function handlePluginLoginSuccess(payload) {
    const response = await postGuard("/plugin/login-success", payload);
    return { status: "success", data: response };
}

async function handleForceNameSync(payload) {
    let browserId = payload.browser_id || payload.bit_id || payload.window_id || "";
    let profileId = payload.profile_id || "";
    let handle = normalizeHandle(payload.handle);

    if (!browserId || !handle) {
        const storage = await chrome.storage.local.get(["matrix_bit_id", "matrix_window_id", "matrix_worker_id"]);
        browserId = browserId || storage.matrix_bit_id || storage.matrix_window_id || "";
        profileId = profileId || storage.matrix_worker_id || "";
        if (!handle && storage.matrix_worker_id) {
            handle = normalizeHandle(storage.matrix_worker_id);
        }
    }

    if (!handle) {
        const storage = await chrome.storage.local.get(["matrix_bit_id", "matrix_window_id", "matrix_worker_id"]);
        return {
            status: "error",
            message:
                "missing handle | bit_id=" +
                (storage.matrix_bit_id || "") +
                " | window_id=" +
                (storage.matrix_window_id || "") +
                " | worker_id=" +
                (storage.matrix_worker_id || ""),
        };
    }

    const response = await postGuard("/plugin/login-success", {
        browser_id: browserId || null,
        handle,
        profile_id: profileId || `@${handle}#guard`,
        plugin_name: "popup_force_sync",
    });
    return { status: "success", data: response };
}

async function handleInstanceRestart(payload) {
    const response = await postGuard("/plugin/instance/restart", payload);
    return { status: "success", data: response };
}

async function handleUserIdentity(request) {
    const storageData = {};
    if (request.profile_id) storageData.matrix_worker_id = request.profile_id;
    if (request.bit_id) storageData.matrix_bit_id = request.bit_id;
    if (request.bit_id && !request.window_id) storageData.matrix_window_id = request.bit_id;
    if (request.window_id) storageData.matrix_window_id = request.window_id;
    if (Object.keys(storageData).length) {
        await chrome.storage.local.set(storageData);
    }
    const payload = {
        profile_id: request.profile_id,
        handle: request.handle,
        bit_id: request.bit_id,
        window_id: request.window_id,
        url: request.url,
        timestamp: request.timestamp,
        plugin_name: request.plugin_name || "content_id_extractor.js",
    };
    const response = await postGuard("/ext/user_id", payload);
    return { status: "success", data: response };
}

async function handleFetchLinks() {
    const url = `${getNasUrl()}/links.txt`;
    const response = await fetch(url, {
        method: "GET",
        headers: {
            "X-API-Token": API_TOKEN,
        },
    });
    if (!response.ok) {
        throw new Error(`fetch_links failed: HTTP ${response.status}`);
    }
    const text = await response.text();
    return { status: "success", data: text };
}

async function pollEngineCommands() {
    try {
        const url = getGuardAgentUrl() + '/plugin/engine/pending';
        const resp = await fetch(url, {
            signal: AbortSignal.timeout(3000),
            headers: {
                "X-API-Token": API_TOKEN,
            },
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (!data.commands || !data.commands.length) return;
        for (const cmd of data.commands) {
            if (cmd.task_id || cmd.action_plan || cmd.target || cmd.copy_payload) {
                const syntheticTask = {
                    task_id: cmd.task_id || null,
                    script_name: cmd.script_name || null,
                    action_plan: Array.isArray(cmd.action_plan) ? cmd.action_plan : [],
                    target: cmd.target || {},
                    copy_payload: cmd.copy_payload || null,
                };
                await chrome.storage.local.set({
                    matrix_current_task: syntheticTask,
                    matrix_current_task_id: cmd.task_id || null,
                    matrix_current_action_plan: Array.isArray(cmd.action_plan) ? cmd.action_plan : [],
                    matrix_current_target: cmd.target || {},
                    matrix_current_copy_payload: cmd.copy_payload || null,
                });
            }
            const action = cmd.command === 'start' ? 'start_engine' : 'stop_engine';
            const tabs = await chrome.tabs.query({ url: ['*://x.com/*', '*://twitter.com/*'] });
            for (const tab of tabs) {
                try { chrome.tabs.sendMessage(tab.id, { action, payload: cmd }); } catch {}
            }
        }
    } catch {}
}

async function sendFallbackHeartbeat() {
    const result = await chrome.storage.local.get(["matrix_last_heartbeat", "matrix_last_heartbeat_time"]);
    const payload = result.matrix_last_heartbeat;
    const lastTime = result.matrix_last_heartbeat_time || 0;
    if (!payload) {
        return;
    }
    if (Date.now() - lastTime < 8000) {
        return;
    }
    try {
        await postGuard("/ext/heartbeat", payload);
    } catch (error) {
        console.warn("[background] fallback heartbeat failed:", error instanceof Error ? error.message : String(error));
    }
}

function normalizeHandle(raw) {
    if (!raw) {
        return "";
    }
    const text = String(raw).trim();
    if (!text) {
        return "";
    }
    if (text.startsWith("@")) {
        return text.slice(1).split("#")[0].toLowerCase();
    }
    return text.toLowerCase();
}

function getNasUrl() {
    return globalThis.__MATRIX_CONFIG && typeof globalThis.__MATRIX_CONFIG.getNAS5000 === "function"
        ? globalThis.__MATRIX_CONFIG.getNAS5000()
        : DEFAULT_NAS_URL;
}

function getGuardAgentUrl() {
    return globalThis.__MATRIX_CONFIG && typeof globalThis.__MATRIX_CONFIG.getGuardAgentUrl === "function"
        ? globalThis.__MATRIX_CONFIG.getGuardAgentUrl()
        : DEFAULT_GUARD_AGENT_URL;
}

async function postGuard(path, payload) {
    const url = `${getGuardAgentUrl()}${path}`;
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-API-Token": API_TOKEN,
        },
        body: JSON.stringify(payload),
    });
    guardAgentAvailable = response.ok;
    const data = await safeJson(response);
    if (!response.ok) {
        throw new Error(data.error || data.message || `guard request failed: HTTP ${response.status}`);
    }
    return data;
}

async function safeJson(response) {
    try {
        return await response.json();
    } catch (error) {
        return {};
    }
}


