const NAS_URL = "http://192.168.0.100:3210";
const BRIDGE_URL = "http://127.0.0.1:54346";

async function updateStatus() {
    // NAS灯
    try {
        const r = await fetch(NAS_URL + "/healthz", { signal: AbortSignal.timeout(3000) });
        document.getElementById("d0").className = "dot g";
    } catch {
        document.getElementById("d0").className = "dot r";
    }

    // 桥接灯
    try {
        const r = await fetch(BRIDGE_URL + "/healthz", { signal: AbortSignal.timeout(2000) });
        document.getElementById("d1").className = "dot g";
    } catch {
        document.getElementById("d1").className = "dot r";
    }

    // 实例灯
    try {
        const s = await chrome.storage.local.get(["matrix_worker_id"]);
        document.getElementById("d2").className = "dot " + (s.matrix_worker_id ? "g" : "y");
    } catch {
        document.getElementById("d2").className = "dot y";
    }

    document.getElementById("ts").textContent = new Date().toLocaleTimeString();
}

document.getElementById("b0").addEventListener("click", updateStatus);
document.getElementById("b1").addEventListener("click", async function () {
    const btn = document.getElementById("b1");
    const orig = btn.textContent;
    btn.textContent = "同步中...";
    btn.disabled = true;
    try {
        const tabs = await chrome.tabs.query({ url: ["*://x.com/*", "*://twitter.com/*"] });
        for (const tab of tabs) {
            try { chrome.tabs.sendMessage(tab.id, { action: "matrix_force_report" }); } catch { }
        }
        await chrome.runtime.sendMessage({ action: "plugin_force_name_sync" });
        setTimeout(updateStatus, 1500);
        setTimeout(function () { btn.textContent = orig; btn.disabled = false; }, 2000);
    } catch (e) {
        btn.textContent = "失败";
        setTimeout(function () { btn.textContent = orig; btn.disabled = false; }, 2000);
    }
});
document.getElementById("b2").addEventListener("click", function () {
    chrome.tabs.create({ url: "http://192.168.0.100:3210/dashboard" });
});
document.getElementById("b3").addEventListener("click", async function () {
    const btn = document.getElementById("b3");
    btn.textContent = "启动中...";
    btn.disabled = true;
    try {
        const tabs = await chrome.tabs.query({ url: ["*://x.com/*", "*://twitter.com/*"] });
        for (const tab of tabs) {
            try { chrome.tabs.sendMessage(tab.id, { action: "start_engine" }); } catch { }
        }
        btn.textContent = "✅ 已启动";
        setTimeout(() => { btn.textContent = "▶ 启动引擎"; btn.disabled = false; }, 2000);
    } catch {
        btn.textContent = "失败";
        setTimeout(() => { btn.textContent = "▶ 启动引擎"; btn.disabled = false; }, 2000);
    }
});
document.getElementById("b4").addEventListener("click", async function () {
    const btn = document.getElementById("b4");
    try {
        const tabs = await chrome.tabs.query({ url: ["*://x.com/*", "*://twitter.com/*"] });
        for (const tab of tabs) {
            try { chrome.tabs.sendMessage(tab.id, { action: "stop_engine" }); } catch { }
        }
    } catch {}
});

updateStatus();
setInterval(updateStatus, 5000);
