// X-Matrix-Bot 插件版 - 自动关注单兵闭环 (V11.11.1 NAS下发模式版)
(function() {
    'use strict';

    // 物理 DOM 单例锁：防止插件双重注入导致"双计费"
    if (document.getElementById('matrix_follow_injected_lock')) return;
    let injectLock = document.createElement('div');
    injectLock.id = 'matrix_follow_injected_lock';
    injectLock.style.display = 'none';
    document.body.appendChild(injectLock);
    
    window.__matrix_follow_injected__ = true;

    // 立即建立端口连接唤醒 Service Worker
    (function wakeSW() {
        try {
            const p = chrome.runtime.connect({ name: 'follow_wake' });
            p.postMessage({ action: 'ping' });
            setTimeout(() => { try { p.disconnect(); } catch(e) {} }, 1000);
        } catch(e) {}
    })();

    // ================= 【诊断日志】 =================
    console.log('[诊断-注入] content_follow.js 已加载');
    console.log('[诊断-环境] chrome 对象:', typeof chrome);
    console.log('[诊断-环境] chrome.runtime:', typeof chrome !== 'undefined' ? typeof chrome.runtime : 'N/A');
    console.log('[诊断-环境] chrome.runtime.sendMessage:', typeof chrome !== 'undefined' && chrome.runtime ? typeof chrome.runtime.sendMessage : 'N/A');

    // ==============================================================================
    // 全局中枢配置
    // ==============================================================================
    // NAS地址已从config.js统一管理，此处不再硬编码


    let isRunning = false;
    let lastMsg = "初始化...";

    // ================= 【实例唯一标识 - 解决多开冲突】 =================
    let instanceId = sessionStorage.getItem('matrix_instance_id');
    if (!instanceId) {
        instanceId = Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem('matrix_instance_id', instanceId);
    }

    // ================= 【0. 标签页绝对隔离机制】 =================
    let myTabId = sessionStorage.getItem('matrix_tab_id');
    if (!myTabId) {
        myTabId = Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem('matrix_tab_id', myTabId);
    }
    
    function isAnotherTabRunning() {
        let activeTab = localStorage.getItem('matrix_active_tab');
        let heartbeat = parseInt(localStorage.getItem('matrix_heartbeat') || '0');
        if (activeTab && activeTab !== myTabId && (Date.now() - heartbeat < 8000)) return true;
        return false;
    }

    function releaseLock() {
        localStorage.setItem('matrix_active_tab', '');
        localStorage.setItem('matrix_heartbeat', '0');
    }

    setInterval(() => {
        if (isRunning) {
            localStorage.setItem('matrix_active_tab', myTabId);
            localStorage.setItem('matrix_heartbeat', Date.now());
        }
    }, 2000);

    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
    const randomInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

    function getMyHandle() {
        let cached = localStorage.getItem('matrix_my_handle');
        if (cached && cached !== "未知账号") return cached;
        let handle = "未知账号";
        let profileLink = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]');
        if (profileLink && profileLink.getAttribute('href')) {
            handle = profileLink.getAttribute('href').replace('/', '').toLowerCase();
        } else {
            const accountBtn = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
            if (accountBtn) {
                const match = accountBtn.innerText.match(/@([\w_]+)/);
                if (match) handle = match[1].toLowerCase();
            }
        }
        if (handle !== "未知账号") localStorage.setItem('matrix_my_handle', handle);
        return handle;
    }

    // 获取带实例标识的 worker_id，解决多开同账号冲突
    function getWorkerId() {
        let handle = getMyHandle();
        if (handle === "未知账号") {
            handle = "推土机_" + Math.floor(Math.random() * 90000 + 10000);
        }
        // 格式: @handle#instanceId，后端会处理成 @handle
        return "@" + handle + "#" + instanceId;
    }

    function getCurrentTaskPayload() {
        try { return JSON.parse(localStorage.getItem('matrix_current_task') || 'null'); }
        catch (e) { return null; }
    }

    function getCurrentActionIndex() {
        var raw = localStorage.getItem('matrix_action_index');
        var parsed = parseInt(raw || '0', 10);
        return isNaN(parsed) ? 0 : parsed;
    }

    function callBackground(action, payload) {
        return new Promise((resolve, reject) => {
            try {
                chrome.runtime.sendMessage({ action, payload: payload || {} }, (response) => {
                    if (chrome.runtime.lastError) {
                        reject(new Error(chrome.runtime.lastError.message || 'runtime error'));
                        return;
                    }
                    resolve(response || null);
                });
            } catch (e) {
                reject(e);
            }
        });
    }

    async function guardNextAction() {
        var resp = await callBackground('guard_next_action', {});
        return resp && resp.status === 'success' ? resp.data : null;
    }

    async function guardCompleteAction(actionName, details) {
        var resp = await callBackground('guard_complete_action', {
            action: actionName,
            success: true,
            details: details || {}
        });
        return resp && resp.status === 'success' ? resp.data : null;
    }

    async function guardFailAction(actionName, details) {
        var resp = await callBackground('guard_fail_action', {
            action: actionName,
            error_code: (details && details.error_code) || 'action_failed',
            error_message: (details && details.error_message) || '',
            details: details || {}
        });
        return resp && resp.status === 'success' ? resp.data : null;
    }

    // 通过 background.js 上报战报（避免 Mixed Content）
    function reportToNAS(targetFan, currentCount, dayCount, extra = {}) {
        var currentTask = getCurrentTaskPayload();
        var payload = {
            bot_id: getWorkerId(),
            target: targetFan,
            count: currentCount,
            day_count: dayCount,
            type: "AUTO",
            action_type: "FOLLOW"
        };
        if (currentTask) {
            payload.task_id = currentTask.task_id || null;
            payload.action_plan = Array.isArray(currentTask.action_plan) ? currentTask.action_plan : [];
            payload.action_index = getCurrentActionIndex();
            payload.target_handle = targetFan;
        }
        payload = Object.assign(payload, extra || {});
        try {
            chrome.runtime.sendMessage({
                action: "log_action",
                payload: payload
            }, (response) => {
                if (chrome.runtime.lastError) {
                    console.log('[战报] Service Worker 未就绪');
                }
            });
        } catch(e) {}
    }

    // ================= 【2. 记账与双重风控雷达】 =================
    function getBeijingDateString() {
        const now = new Date();
        const bj = new Date(now.getTime() + 8 * 60 * 60 * 1000);
        return `${bj.getUTCFullYear()}/${bj.getUTCMonth()+1}/${bj.getUTCDate()}`;
    }

    function getAccountStats() {
        const handle = getMyHandle();
        const key = `matrix_stats_${handle}`;
        let stats = JSON.parse(localStorage.getItem(key) || '{"date":"","follows_today":0,"day_count":0}');
        let today = getBeijingDateString();
        if (stats.date !== today) {
            stats.date = today; stats.follows_today = 0; stats.day_count++;
            localStorage.setItem(key, JSON.stringify(stats));
        }
        return stats;
    }

    function incrementFollowCount() {
        const handle = getMyHandle();
        const key = `matrix_stats_${handle}`;
        let stats = getAccountStats();
        stats.follows_today++;
        localStorage.setItem(key, JSON.stringify(stats));
        return stats.follows_today;
    }

    function getDailyLimit(dayCount) {
        if (dayCount <= 1) return randomInt(85, 105);   
        if (dayCount === 2) return randomInt(140, 170); 
        return randomInt(280, 295);                     
    }

    function checkLimits() {
        const toasts = document.querySelectorAll('[data-testid="toast"]');
        const modals = document.querySelectorAll('[role="alertdialog"]');
        const allAlerts = [...toasts, ...modals];

        for (let t of allAlerts) {
            let txt = (t.innerText || "").toLowerCase();
            if (txt.includes("你暂时不能关注更多用户") || txt.includes("无法再关注") || txt.includes("unable to follow more") || txt.includes("达到每天的关注上限") || txt.includes("不能再关注")) {
                return 'HARD';
            }
            if (txt.includes("速度限制") || txt.includes("rate limit") || txt.includes("稍后再试") || txt.includes("try again") || txt.includes("limit")) {
                return 'SOFT';
            }
        }
        return 'NONE';
    }

    function getMatrixCooldownUntil() {
        return parseInt(localStorage.getItem('matrix_global_cooldown_until') || '0', 10) || 0;
    }

    function setMatrixCooldown(ms) {
        localStorage.setItem('matrix_global_cooldown_until', (Date.now() + ms).toString());
    }

    function getNextGlobalFollowTime() {
        return parseInt(localStorage.getItem('matrix_global_next_follow_time') || '0', 10) || 0;
    }

    function setNextGlobalFollowTime(ms) {
        localStorage.setItem('matrix_global_next_follow_time', (Date.now() + ms).toString());
    }

    async function waitForGlobalFollowSlot() {
        const nextTime = getNextGlobalFollowTime();
        const now = Date.now();
        if (now < nextTime) {
            const waitMs = nextTime - now + randomInt(800, 1800);
            updateStats(`矩阵节奏控制，等待 ${Math.round(waitMs/1000)}s`);
            await sleep(waitMs);
        }
    }

    // ================= 【3. UI 与 手动改配额 + 自动启动】 =================
    const AUTO_START_KEY = 'matrix_follow_auto_start_enabled';

    function isAutoStartEnabled() {
        return localStorage.getItem(AUTO_START_KEY) === 'true';
    }

    function setAutoStartEnabled(enabled) {
        localStorage.setItem(AUTO_START_KEY, enabled ? 'true' : 'false');
    }

    const toggleBtn = document.createElement('button');
    toggleBtn.innerText = '▶';
    toggleBtn.style.cssText = `position: fixed; bottom: 30px; right: 30px; z-index: 2147483647; width: 40px; height: 40px; border-radius: 50%; border: none; background: ${isAutoStartEnabled() ? '#00ba7c' : '#1d9bf0'}; color: white; font-size: 18px; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(0,0,0,0.5); opacity: 1 !important; visibility: visible !important;`;
    toggleBtn.title = isAutoStartEnabled() ? '关注引擎 (自动启动模式)' : '关注引擎 (手动模式)';
    document.body.appendChild(toggleBtn);

    const statsUi = document.createElement('div');
    statsUi.style.cssText = `position: fixed; bottom: 80px; right: 30px; z-index: 2147483647; background: rgba(0,0,0,0.9); color: #cfd9de; padding: 12px; border-radius: 10px; font-size: 13px; font-family: monospace; display: none; border: 1px solid #333; line-height: 1.8; box-shadow: 0 8px 20px rgba(0,0,0,0.5); transition: width 0.2s ease; overflow: hidden;`;
    document.body.appendChild(statsUi);

    let isMinimized = localStorage.getItem('matrix_ui_minimized') === 'true';

    statsUi.addEventListener('click', (e) => {
        if (e.target.classList.contains('matrix-toggle-btn')) {
            isMinimized = !isMinimized;
            localStorage.setItem('matrix_ui_minimized', isMinimized);
            updateStats(lastMsg);
        }
        else if (e.target.id === 'matrix-edit-quota') {
            let currentStats = getAccountStats();
            let newVal = prompt("手动补回配额：\n请输入当前实际已关注的数量（数字）：", currentStats.follows_today);
            if (newVal !== null && !isNaN(parseInt(newVal))) {
                currentStats.follows_today = parseInt(newVal);
                localStorage.setItem(`matrix_stats_${getMyHandle()}`, JSON.stringify(currentStats));
                alert(`修改成功！当前进度已强制设为：${currentStats.follows_today}`);
                updateStats(lastMsg);
            }
        }
        else if (e.target.id === 'matrix-nas-config-btn') {
            // V11.6.0: 移除 5050 端口配置，统一使用 5678 端口
            let current5000 = window.__MATRIX_CONFIG ? window.__MATRIX_CONFIG.getNAS5000() : 'http://192.168.0.100:5678';
            let new5000 = prompt("设置 NAS 服务地址 (端口5678):\n当前: " + current5000 + "\n留空保持不变", current5000);
            if (new5000 !== null && new5000.trim() !== '') {
                if (window.__MATRIX_CONFIG) {
                    window.__MATRIX_CONFIG.set('NAS_5000', new5000.trim(), function(err) {
                        if (err) {
                            alert('保存失败: ' + err.message);
                        } else {
                            alert('✅ NAS地址已更新！刷新页面后生效。');
                            updateStats(lastMsg);
                        }
                    });
                }
            }
        }
    });

    function updateStats(msg) {
        lastMsg = msg;
        const stats = getAccountStats();
        const limit = getDailyLimit(stats.day_count);
        let currentTarget = localStorage.getItem('matrix_current_creator') || '空';
        let statusIcon = isRunning ? '<span style="font-weight:bold; color:#00ba7c;">运行中...</span>' : '<span style="font-weight:bold; color:#f91880;">已暂停</span>';

        if (isMinimized) {
            statsUi.style.width = '140px';
            statsUi.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center;">${statusIcon}<span class="matrix-toggle-btn" style="cursor:pointer; color:#1d9bf0;">[展开]</span></div>`;
        } else {
            statsUi.style.width = '230px';
            let dayBadge = `<span style="background: linear-gradient(90deg, #f91880, #8a2be2); color: white; padding: 2px 6px; border-radius: 4px;">第${stats.day_count}天</span>`;
            let autoStartChecked = isAutoStartEnabled() ? 'checked' : '';
            statsUi.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid #444; padding-bottom: 6px; margin-bottom: 6px;">
                    ${dayBadge} <span class="matrix-toggle-btn" style="cursor:pointer; color:#1d9bf0;">[-] 收起</span>
                </div>
                <div>账号: @${getMyHandle()}</div>
                <div>配额: <span id="matrix-edit-quota" style="cursor:pointer; color:#00ba7c; text-decoration:underline; font-weight:bold;" title="点击修改">${stats.follows_today}</span> / ${limit}</div>
                <div>目标: @${currentTarget}</div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:2px; font-size:12px;">
                    <span>NAS: <span id="matrix-nas-status" style="color:#888;">检测中...</span></span>
                    <span id="matrix-nas-config-btn" style="cursor:pointer; color:#1d9bf0;">⚙️设置</span>
                </div>
                <div style="border-top:1px dashed #555; margin-top:5px; padding-top:5px;">
                    <label style="display:flex; align-items:center; gap:6px; cursor:pointer; font-size:12px;">
                        <input type="checkbox" id="matrix-follow-auto-start-checkbox" ${autoStartChecked} style="cursor:pointer;">
                        <span style="color:${isAutoStartEnabled() ? '#00ba7c' : '#888'};">🤖 页面打开时自动启动</span>
                    </label>
                </div>
                <div style="border-top:1px dashed #555; color:${isRunning ? '#f91880' : '#888'}; font-weight:bold; margin-top:5px; padding-top:5px;">${isRunning ? msg : '引擎已停止'}</div>
            `;
            // 绑定复选框事件
            setTimeout(() => {
                const cb = document.getElementById('matrix-follow-auto-start-checkbox');
                if (cb) {
                    cb.addEventListener('change', (e) => {
                        const enabled = e.target.checked;
                        setAutoStartEnabled(enabled);
                        toggleBtn.style.background = enabled ? '#00ba7c' : '#1d9bf0';
                        toggleBtn.title = enabled ? '关注引擎 (自动启动模式)' : '关注引擎 (手动模式)';
                        updateStats(lastMsg);
                        const toast = document.getElementById('auto-dm-toast') || document.createElement('div');
                        if (!toast.id) {
                            toast.id = 'auto-dm-toast';
                            toast.style.cssText = 'position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: ' + (enabled ? '#00ba7c' : '#f91880') + '; color: white; padding: 12px 24px; border-radius: 8px; font-size: 16px; font-weight: bold; z-index: 999999; pointer-events: none; box-shadow: 0 4px 12px rgba(0,0,0,0.2);';
                            document.body.appendChild(toast);
                        }
                        toast.innerText = enabled ? '🤖 关注引擎自动启动已开启！' : '🔒 关注引擎自动启动已关闭';
                        toast.style.background = enabled ? '#00ba7c' : '#f91880';
                        toast.style.display = 'block';
                        setTimeout(() => { toast.style.display = 'none'; }, 2000);
                    });
                }
            }, 0);
        }
        statsUi.style.display = 'block';
        // 检测NAS连通状态（仅在展开面板时）
        if (!isMinimized) {
            setTimeout(checkNASStatus, 100);
        }
    }

    // ================= 【NAS地址显示（content script 不能发 HTTP 请求到 HTTPS 页面）】 =================
    function checkNASStatus() {
        const el = document.getElementById('matrix-nas-status');
        if (!el) return;
        const url = (window.__MATRIX_CONFIG ? window.__MATRIX_CONFIG.getNAS5000() : 'http://192.168.0.100:5000');
        // 只显示地址，不做连通检测（避免 HTTPS 页面的 Mixed Content 拦截）
        el.innerHTML = '<span style="color:#888; font-size:11px;">' + url.replace('http://', '') + '</span>';
    }

    setInterval(() => {
        // 看门狗：只在引擎运行时检查页面健康
        if (!isRunning) return;
        let lastHealth = parseInt(sessionStorage.getItem('matrix_watchdog_time') || Date.now());
        let cr = localStorage.getItem('matrix_current_creator') || "unknown";
        let currentPath = window.location.pathname.toLowerCase();
        
        if (document.querySelector('[data-testid="UserCell"]') || currentPath === '/' + cr) {
            sessionStorage.setItem('matrix_watchdog_time', Date.now());
        } else if (Date.now() - lastHealth > 35000) {
            updateStats("【防卡死】触发，强力刷新！");
            location.href = window.location.href + (window.location.href.includes('?') ? '&' : '?') + '_t=' + Date.now();
        }
    }, 5000);

    // ================= 【4. 仿生引擎逻辑】 =================
    async function runEngine() {
        while (isRunning) {
            const stats = getAccountStats();
            const limit = getDailyLimit(stats.day_count);
            if (stats.follows_today >= limit) { updateStats("今日总目标达成！下班"); stopBot(); return; }

            let globalCooldown = getMatrixCooldownUntil();
            if (Date.now() < globalCooldown) {
                let remaining = Math.round((globalCooldown - Date.now()) / 1000);
                updateStats(`矩阵级冷却中，剩余 ${remaining}s`);
                await sleep(Math.min(20000, remaining * 1000));
                continue;
            }

            let startLimit = checkLimits();
            if (startLimit === 'HARD') {
                setMatrixCooldown(randomInt(3 * 3600000, 4 * 3600000));
                updateStats("触发最高风控！脚本已紧急熔断！");
                alert("紧急停止：检测到推特最高风控（你暂时不能关注更多用户）！为保护账号，脚本已自动挂起！");
                stopBot();
                return;
            } else if (startLimit === 'SOFT') {
                let coffee = randomInt(900000, 1020000); 
                setMatrixCooldown(coffee);
                updateStats(`触碰软风控！进入耗尽型休眠 ${Math.round(coffee/60000)}min...`);
                toggleBtn.innerText = '💤'; toggleBtn.style.background = '#8a2be2';
                await sleep(coffee);
                location.reload(); 
                return;
            }

            let step = localStorage.getItem('matrix_step') || 'INIT';

            if (step === 'INIT') {
                let path = window.location.pathname;
                if (path.includes('/followers') && !path.includes('/verified_followers')) {
                    localStorage.setItem('matrix_current_creator', path.split('/')[1]);
                    localStorage.setItem('matrix_step', 'SCAN');
                    updateStats("原地开工，锁定目标...");
                } else { 
                    localStorage.setItem('matrix_step', 'FETCH'); 
                }
                continue;
            }

            if (step === 'FETCH') {
                let fetchWait = randomInt(3000, 5000); 
                updateStats(`等待 NAS 5000 端口发号 (${Math.round(fetchWait/1000)}s)...`); 
                await sleep(fetchWait);
                
                try {
                    // 先通过 background.js 获取任务 (保持兼容)，再通过 next-action 获取当前步骤
                    let taskResponse = await new Promise((resolve, reject) => {
                        let attempts = 0;
                        function doFetch() {
                            chrome.runtime.sendMessage(
                                { action: "fetch_task" },
                                (response) => {
                                    if (chrome.runtime.lastError) {
                                        if (attempts < 2) {
                                            attempts++;
                                            setTimeout(doFetch, 2000);
                                            return;
                                        }
                                        reject(new Error("Service Worker 未就绪 (重试" + attempts + "次)"));
                                        return;
                                    }
                                    if (response && response.status === "success") {
                                        resolve(response);
                                    } else {
                                        reject(new Error("获取失败"));
                                    }
                                }
                            );
                        }
                        doFetch();
                        setTimeout(() => reject(new Error("fetch_task 超时")), 12000);
                    });
                    
                    let rawCreator = taskResponse && taskResponse.data ? taskResponse.data : "EMPTY";
                    let taskPayload = taskResponse && taskResponse.task ? taskResponse.task : getCurrentTaskPayload();

                    if (!rawCreator || rawCreator.trim() === "EMPTY" || rawCreator.trim().toLowerCase() === "empty") { 
                        updateStats("弹药库空或通信被拦截！(检查 5000 端口或权限)"); 
                        stopBot(); 
                        return; 
                    }
                    
                    let creator = rawCreator.trim().replace('@','').toLowerCase();
                    localStorage.setItem('matrix_current_creator', creator);
                    var nextAction = await guardNextAction();
                    var actionPlan = taskPayload && Array.isArray(taskPayload.action_plan) ? taskPayload.action_plan : [];
                    if (nextAction && nextAction.action === 'follow') {
                        localStorage.setItem('matrix_step', 'ACTION_FOLLOW');
                        localStorage.setItem('matrix_action_index', String(nextAction.action_index || 0));
                        window.location.href = `https://x.com/${creator}`;
                    } else if (actionPlan.length > 0) {
                        // 任务存在但当前不是 follow，则把 follow 引擎挂起，等待 chat 引擎处理
                        updateStats("当前任务下一步不是 follow，等待 chat 引擎...");
                        stopBot();
                        return;
                    } else {
                        localStorage.setItem('matrix_step', 'SEARCH');
                        window.location.href = `https://x.com/search?q=%40${creator}&f=user`;
                    }
                } catch (e) {
                    updateStats("NAS连接失败！请检查 5000 端口状态"); 
                    stopBot(); 
                    return; 
                }
                return;
            }

// V11.10: single task follow mode
            if (step === 'ACTION_FOLLOW') {
                var cr = (localStorage.getItem('matrix_current_creator') || '').trim().toLowerCase();
                var currentPath = window.location.pathname.toLowerCase();
                if (!currentPath.includes(cr)) {
                    await sleep(3000);
                    if (!window.location.pathname.toLowerCase().includes(cr)) {
                        window.location.href = 'https://x.com/' + cr;
                        return;
                    }
                }
                var profileWait = randomInt(2000, 3500);
                await sleep(profileWait);
                var followBtn = document.querySelector('[data-testid="followButton"]');
                if (!followBtn) {
                    reportToNAS(cr, getAccountStats().follows_today, getAccountStats().day_count);
                    try {
                        var next1 = await guardCompleteAction('follow', { reason: 'follow_button_missing' });
                        if (next1 && next1.status === 'all_completed') {
                            localStorage.removeItem('matrix_current_task');
                            localStorage.removeItem('matrix_current_task_id');
                            stopBot();
                            return;
                        }
                    } catch (e) {}
                    localStorage.setItem('matrix_step', 'FETCH');
                    continue;
                }
                var testId = (followBtn.getAttribute('data-testid') || '').toLowerCase();
                if (testId.includes('unfollow')) {
                    reportToNAS(cr, getAccountStats().follows_today, getAccountStats().day_count);
                    try {
                        var next2 = await guardCompleteAction('follow', { reason: 'already_followed' });
                        if (next2 && next2.status === 'all_completed') {
                            localStorage.removeItem('matrix_current_task');
                            localStorage.removeItem('matrix_current_task_id');
                            stopBot();
                            return;
                        }
                    } catch (e) {}
                    localStorage.setItem('matrix_step', 'FETCH');
                    continue;
                }
                followBtn.click();
                await sleep(2000);
                var postClickLimit = checkLimits();
                if (postClickLimit !== 'NONE') {
                    reportToNAS(cr, getAccountStats().follows_today, getAccountStats().day_count, { failed: true });
                    try { await guardFailAction('follow', { error_code: postClickLimit, error_message: 'follow limit hit' }); } catch (e) {}
                    stopBot();
                    return;
                }
                var count = incrementFollowCount();
                reportToNAS(cr, count, getAccountStats().day_count);
                try {
                    var next3 = await guardCompleteAction('follow', { count: count, target_handle: cr });
                    if (next3 && next3.status === 'all_completed') {
                        localStorage.removeItem('matrix_current_task');
                        localStorage.removeItem('matrix_current_task_id');
                        stopBot();
                        return;
                    }
                    if (next3 && (next3.action === 'icebreaker' || next3.action === 'ad' || next3.action === 'chat')) {
                        localStorage.setItem('matrix_step', 'FETCH');
                    } else {
                        localStorage.setItem('matrix_step', 'FETCH');
                    }
                } catch (e) {
                    localStorage.setItem('matrix_step', 'FETCH');
                }
                await sleep(randomInt(2000, 4000));
                window.location.href = 'https://x.com/home';
                return;
            }

                        if (step === 'SEARCH') {
                let searchWait = randomInt(4000, 6000); 
                updateStats(`阅读搜索结果 (${Math.round(searchWait/1000)}s)...`); 
                await sleep(searchWait);
                
                window.scrollBy({ top: randomInt(150, 350), behavior: 'smooth' });
                await sleep(randomInt(1200, 2000));

                let cr = (localStorage.getItem('matrix_current_creator') || "").trim().replace('@','').toLowerCase();
                let targetLink = null;
                
                for(let i=0; i<10; i++) {
                    let cells = document.querySelectorAll('[data-testid="UserCell"]');
                    for (let cell of cells) {
                        let rawText = cell.innerText || "";
                        let match = rawText.match(/@([\w_]+)/); 
                        if (match && match[1].toLowerCase() === cr) {
                            targetLink = cell.querySelector('a[role="link"]') || cell;
                            break;
                        }
                    }
                    if(!targetLink) targetLink = document.querySelector(`a[href^="/${cr}" i]`);
                    if(targetLink) break;
                    await sleep(1000);
                }
                
                if (targetLink) {
                    updateStats("发现目标！锁定中...");
                    localStorage.setItem('matrix_step', 'PROFILE');
                    
                    targetLink.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    await sleep(randomInt(1000, 1800)); 
                    
                    let currentUrl = window.location.href;
                    targetLink.click();
                    
                    let navigated = false;
                    for(let i=0; i<10; i++) {
                        await sleep(500);
                        if(window.location.href !== currentUrl) { navigated = true; break; }
                    }
                    
                    if (!navigated) {
                        updateStats("前端响应迟缓，启动安全跳跃...");
                        window.location.href = `/${cr}`;
                        return; 
                    }
                    await sleep(randomInt(3500, 5000)); 
                } else { 
                    updateStats("当前页未找到博主，重新领号...");
                    localStorage.setItem('matrix_step', 'FETCH'); 
                }
                continue;
            }

            if (step === 'PROFILE') {
                let cr = (localStorage.getItem('matrix_current_creator') || "").trim().toLowerCase();
                
                let currentUrl = window.location.href.toLowerCase();
                let bodyText = document.body.innerText.toLowerCase();
                if (!currentUrl.includes(cr) && !bodyText.includes(cr)) {
                    updateStats("页面数据异常，重新核对...");
                    await sleep(3000);
                }

                let profileWait = randomInt(2500, 4500);
                updateStats(`阅读博主主页...`);
                
                window.scrollBy({ top: randomInt(400, 800), behavior: 'smooth' }); 
                await sleep(profileWait);
                window.scrollBy({ top: randomInt(200, 400), behavior: 'smooth' }); 
                await sleep(randomInt(1000, 2000));

                updateStats("滑动至顶部，准备进入粉丝页...");
                window.scrollTo({ top: 0, behavior: 'smooth' });
                await sleep(randomInt(2000, 3500)); 

                let flink = null;
                for(let i=0; i<10; i++) {
                    let allLinks = document.querySelectorAll('a[role="link"], a');
                    for (let a of allLinks) {
                        let href = (a.getAttribute('href') || "").toLowerCase();
                        if (href === `/${cr}/followers` || href === `/${cr}/verified_followers`) {
                            flink = a;
                            break;
                        }
                    }
                    if(flink) break;
                    await sleep(1000);
                }
                
                if (flink) { 
                    localStorage.setItem('matrix_step', 'NAVIGATE_TAB'); 
                    updateStats("锁定列表入口，模拟点击...");
                    
                    flink.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    await sleep(randomInt(1000, 2000));
                    
                    let preClickUrl = window.location.href;
                    flink.click(); 
                    
                    let navigated = false;
                    for(let i=0; i<10; i++) {
                        await sleep(500);
                        if(window.location.href !== preClickUrl) { navigated = true; break; }
                    }
                    if (!navigated) {
                        updateStats("强制跳转...");
                        window.location.href = `/${cr}/followers`;
                        return;
                    }
                    
                    await sleep(randomInt(3000, 5000)); 
                } else { 
                    updateStats("未找到入口，撤退...");
                    localStorage.setItem('matrix_step', 'FETCH'); 
                }
                continue;
            }

            if (step === 'NAVIGATE_TAB') {
                let cr = (localStorage.getItem('matrix_current_creator') || "").trim().toLowerCase();
                updateStats("确认粉丝列表列...");
                
                let tabs = [];
                for(let i=0; i<10; i++) {
                    tabs = document.querySelectorAll('[role="tab"]');
                    if(tabs.length > 0) break;
                    await sleep(1000);
                }

                let targetTab = null;
                for (let tab of tabs) {
                    let href = (tab.getAttribute('href') || "").toLowerCase();
                    if (href === `/${cr}/followers`) {
                        targetTab = tab;
                        break;
                    }
                }

                if (targetTab) {
                    if (targetTab.getAttribute('aria-selected') !== 'true') {
                        updateStats("发现列偏离，切换至纯关注者列...");
                        targetTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        await sleep(randomInt(800, 1500));
                        targetTab.click();
                        await sleep(randomInt(3000, 5000)); 
                    } else {
                        updateStats("已处于关注者列...");
                        await sleep(randomInt(1000, 2000));
                    }
                    
                    localStorage.setItem('matrix_step', 'SCAN');
                    updateStats("寻敌结束，启动狙击模式！");
                    await sleep(randomInt(1000, 2000));
                } else {
                    updateStats("未找到Tab标签，执行强制修正...");
                    window.location.href = `/${cr}/followers`;
                    localStorage.setItem('matrix_step', 'SCAN'); 
                    return;
                }
                continue;
            }

            if (step === 'SCAN') {
                let cells = [];
                updateStats("等待粉丝数据加载...");
                for(let i=0; i<15; i++) {
                    cells = Array.from(document.querySelectorAll('[data-testid="UserCell"]:not([data-matrix-processed="true"])'));
                    if(cells.length > 0) break;
                    await sleep(1000);
                }

                if (cells.length > 0) {
                    let cell = cells[0];
                    let rawText = cell.innerText || "";
                    
                    let followBtn = cell.querySelector('[role="button"][data-testid*="ollow"]');
                    if (!followBtn) {
                        cell.setAttribute('data-matrix-processed', 'true');
                        window.scrollBy({ top: randomInt(30, 60), behavior: 'smooth' }); 
                        await sleep(randomInt(500, 900)); 
                        continue;
                    }

                    let btnText = (followBtn.textContent || followBtn.innerText || "").replace(/\s+/g, "");
                    let testId = (followBtn.getAttribute('data-testid') || "").toLowerCase();
                    let ariaLabel = (followBtn.getAttribute('aria-label') || "").toLowerCase();
                    let isAlreadyFollowed = testId.includes('unfollow') || btnText.includes('正在') || btnText.includes('已关') || btnText.includes('following') || ariaLabel.includes('正在') || ariaLabel.includes('已关注');

                    if (isAlreadyFollowed) {
                        updateStats("已关注，安全跳过...");
                        cell.style.cssText += 'opacity: 0.3 !important; filter: grayscale(100%) !important; border: 1px dashed #00ba7c;';
                        cell.setAttribute('data-matrix-processed', 'true');
                        window.scrollBy({ top: randomInt(35, 75), behavior: 'smooth' });
                        await sleep(randomInt(700, 1200)); 
                        continue;
                    }

                    let lines = rawText.split('\n').map(l => l.trim()).filter(l => l.length > 0);
                    let rawBtnText = followBtn.innerText ? followBtn.innerText.trim() : '';
                    let content = lines.filter(l => l !== rawBtnText).join(' | ');
                    
                    const isJp = /[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]/.test(content);
                    const isPureEng = /[a-zA-Z]/.test(content) && !isJp;
                    const isSubstantial = content.length > 8;

                    if (isPureEng || !isJp || !isSubstantial) {
                        cell.style.cssText += 'opacity: 0.15; filter: grayscale(100%); border: 1px solid red;'; 
                        updateStats("【防线】非目标号，剔除..."); 
                        cell.setAttribute('data-matrix-processed', 'true');
                        window.scrollBy({ top: randomInt(35, 75), behavior: 'smooth' });
                        await sleep(randomInt(700, 1200)); 
                        continue;
                    } 
                    
                    let readIntroWait = randomInt(3000, 5500);
                    updateStats(`深度阅读简介 (${Math.round(readIntroWait/1000)}s)...`); 
                    await sleep(readIntroWait);
                    
                    await waitForGlobalFollowSlot();
                    followBtn.click();

                    await sleep(2000);
                    let postClickLimit = checkLimits();
                    if (postClickLimit === 'HARD') {
                        setMatrixCooldown(randomInt(3 * 3600000, 4 * 3600000));
                        updateStats("触发最高风控！脚本已紧急熔断！");
                        alert("紧急停止：检测到推特最高风控（你暂时不能关注更多用户）！为保护账号，脚本已自动挂起！");
                        stopBot();
                        return;
                    } else if (postClickLimit === 'SOFT') {
                        let coffee = randomInt(900000, 1020000); 
                        setMatrixCooldown(coffee);
                        updateStats(`触碰软风控！进入耗尽型休眠 ${Math.round(coffee/60000)}min...`);
                        toggleBtn.innerText = '💤'; toggleBtn.style.background = '#8a2be2';
                        await sleep(coffee);
                        location.reload(); 
                        return;
                    }

                    let count = incrementFollowCount();
                    let tid = (rawText.match(/@([\w_]+)/) || ["","未知"])[1];
                    reportToNAS(tid, count, stats.day_count);
                    setNextGlobalFollowTime(randomInt(12000, 19000));
                    
                    cell.setAttribute('data-matrix-processed', 'true'); 

                    let rest = randomInt(18000, 24000); 
                    updateStats(`操作完毕，原地磐石静止伪装 (${Math.round(rest/1000)}s)...`);
                    await sleep(rest);

                    window.scrollBy({ top: randomInt(50, 80), behavior: 'smooth' });
                    await sleep(randomInt(1000, 1500));
                } else {
                    updateStats("向下寻找新粉中...");
                    let beforeScroll = window.scrollY;
                    window.scrollBy({ top: randomInt(250, 400), behavior: 'smooth' }); 
                    await sleep(randomInt(2500, 4000));
                    
                    let afterScroll = window.scrollY;
                    if (Math.abs(afterScroll - beforeScroll) < 10) {
                        updateStats("确认到底，本页收割完毕！");
                        localStorage.setItem('matrix_step', 'FETCH'); 
                        await sleep(randomInt(2500, 4000));
                    }
                }
                continue;
            }
        }
    }

    function stopBot() { 
        isRunning = false; 
        toggleBtn.innerText = '▶'; 
        sessionStorage.setItem('matrix_tab_running', 'false'); 
        releaseLock(); 
        updateStats("引擎已手动或风控停止"); 
    }

    // 【Tab 隔离】检查是否在别人的 followers 页面（关注脚本专属）
    function isOthersFollowersPage() {
        let path = window.location.pathname;
        if (!path.includes('/followers') || path.includes('/verified_followers')) return false;
        let pathHandle = path.split('/')[1].toLowerCase();
        let myHandle = getMyHandle();
        if (!myHandle || myHandle === '未知账号') {
            console.log('[隔离] 无法确定当前用户，关注脚本暂不启动');
            return false;
        }
        return pathHandle !== myHandle;
    }

    function tryAutoStart() {
        // 自动启动条件检查
        if (!isAutoStartEnabled()) return false;
        if (isRunning) return false;
        if (isAnotherTabRunning()) {
            console.log('[自动启动] 另一个Tab正在运行，跳过');
            return false;
        }
        const s = getAccountStats();
        if (s.follows_today >= getDailyLimit(s.day_count)) {
            console.log('[自动启动] 配额已满，跳过');
            return false;
        }
        // NAS 下发模式：从任何页面均可启动
        if (!isOthersFollowersPage()) {
            console.log('[自动启动] 首页/NAS 下发模式，引擎从 FETCH 开始');
            localStorage.setItem('matrix_step', 'FETCH');
            localStorage.removeItem('matrix_current_creator');
        } else {
            console.log('[自动启动] 粉丝页模式，引擎从 SCAN 开始');
            localStorage.setItem('matrix_current_creator', window.location.pathname.split('/')[1]);
            localStorage.setItem('matrix_step', 'SCAN');
        }
        isRunning = true;
        toggleBtn.innerText = '⏹';
        sessionStorage.setItem('matrix_tab_running', 'true');
        
        // 显示自动启动提示
        const toast = document.getElementById('auto-dm-toast') || document.createElement('div');
        if (!toast.id) {
            toast.id = 'auto-dm-toast';
            toast.style.cssText = 'position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #00ba7c; color: white; padding: 12px 24px; border-radius: 8px; font-size: 16px; font-weight: bold; z-index: 999999; pointer-events: none; box-shadow: 0 4px 12px rgba(0,0,0,0.2);';
            document.body.appendChild(toast);
        }
        toast.innerText = '🤖 关注引擎自动启动！';
        toast.style.display = 'block';
        setTimeout(() => { toast.style.display = 'none'; }, 2000);
        
        runEngine();
        return true;
    }

    // 接收来自 background 或 popup 的启动信号
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === 'start_engine' && !isRunning) {
            // 只响应 follow 引擎命令，chat 引擎命令跳过
            var cmdScript = request.payload && request.payload.script_name;
            if (cmdScript && cmdScript !== 'follow') return;
            if (request.payload && request.payload.task_id) {
                localStorage.setItem('matrix_current_task', JSON.stringify({
                    task_id: request.payload.task_id || '',
                    script_name: request.payload.script_name || 'follow',
                    action_plan: request.payload.action_plan || [],
                    target: request.payload.target || {},
                    copy_payload: request.payload.copy_payload || null,
                }));
                localStorage.setItem('matrix_current_task_id', request.payload.task_id || '');
                localStorage.setItem('matrix_current_action_plan', JSON.stringify(request.payload.action_plan || []));
                localStorage.setItem('matrix_current_target_payload', JSON.stringify(request.payload.target || {}));
                localStorage.setItem('matrix_current_copy_payload', JSON.stringify(request.payload.copy_payload || null));
            }
            localStorage.setItem('matrix_step', 'FETCH');
            isRunning = true;
            toggleBtn.innerText = '⏹';
            sessionStorage.setItem('matrix_tab_running', 'true');
            runEngine();
            sendResponse({ status: 'started' });
            return true;
        }
        if (request.action === 'stop_engine' && isRunning) {
            stopBot();
            sendResponse({ status: 'stopped' });
        }
    });

    toggleBtn.addEventListener('click', () => {
        if (!isRunning) {
            if (isAnotherTabRunning()) {
                alert("保护机制触发：\n检测到当前浏览器实例中，已有另一个标签页正在执行关注任务。");
                return;
            }
            const s = getAccountStats(); 
            if(s.follows_today >= getDailyLimit(s.day_count)) { 
                alert("全局配额已满！如需强制继续，请点击面板上的数字手动修改配额。"); 
                statsUi.style.display = 'block';
                updateStats("配额已满，等待手工修正");
                return; 
            }
            // NAS 下发模式：从任何页面均可启动
            if (!isOthersFollowersPage()) {
                // 非粉丝页 → FETCH 模式（从 NAS 拉取任务）
                localStorage.setItem('matrix_step', 'FETCH');
                localStorage.removeItem('matrix_current_creator');
            } else {
                // 粉丝页 → SCAN 模式（扫描粉丝列表）
                let path = window.location.pathname;
                localStorage.setItem('matrix_current_creator', path.split('/')[1]);
                localStorage.setItem('matrix_step', 'SCAN');
            }
            isRunning = true; 
            toggleBtn.innerText = '⏹'; 
            sessionStorage.setItem('matrix_tab_running', 'true'); 
            runEngine();
        } else { stopBot(); }
    });
    
    updateStats(lastMsg); 
    
    // 页面加载后：先尝试恢复之前的运行状态，再尝试自动启动
    setTimeout(() => {
        // 1. 先检查是否需要恢复之前的运行状态（页面刷新等情况）
        if (!isRunning && sessionStorage.getItem('matrix_tab_running') === 'true' && !isAnotherTabRunning()) { 
            isRunning = true; toggleBtn.innerText = '⏹'; runEngine(); 
            return;
        }
        // 2. 如果之前没有运行，尝试自动启动
        tryAutoStart();
    }, randomInt(1000, 2500));
    
    // ========== 【批量同步本地累计关注数到 NAS】 ==========
    setTimeout(() => {
        let stats = getAccountStats();
        let workerId = getWorkerId();
        if (stats.follows_today > 0) {
            console.log(`[批量同步] 本地关注累计: ${stats.follows_today}，正在上传到 NAS...`);
            try {
                chrome.runtime.sendMessage({
                    action: "send_report",
                    payload: {
                        worker_id: workerId,
                        engine: "follow",
                        status: "批量同步本地统计",
                        detail: `关注${stats.follows_today}/Day${stats.day_count}`,
                        stats: {
                            added: stats.follows_today
                        }
                    }
                }, (response) => {
                    if (chrome.runtime.lastError) {
                        console.error('[批量同步] Service Worker 未就绪');
                    } else if (response && response.status === 'success') {
                        console.log('[批量同步] ✅ 关注数上传成功！');
                    } else {
                        console.warn('[批量同步] 上传失败:', response);
                    }
                });
            } catch(e) {
                console.error('[批量同步] 异常:', e);
            }
        }
    }, 4000);

    // ==============================================================================
    // 探针模块与大屏心跳 (V11.5 修复：休眠期间持续上报，不显示掉线)
    // ==============================================================================
    setInterval(() => {
        let workerId = sessionStorage.getItem('matrix_worker_id');
        
        if (!workerId || workerId.includes('null') || workerId.includes('undefined')) {
            workerId = getWorkerId();
            sessionStorage.setItem('matrix_worker_id', workerId);
        }

        // 检查是否处于全局冷却（风控休眠）
        let globalCooldown = parseInt(localStorage.getItem('matrix_global_cooldown_until') || '0');
        let isCoolingDown = Date.now() < globalCooldown;
        let remainingMs = isCoolingDown ? (globalCooldown - Date.now()) : 0;
        let remainingMin = Math.ceil(remainingMs / 60000);

        // 根据引擎状态设置心跳状态
        let currentStatus, detailStr;
        if (isCoolingDown) {
            currentStatus = "风控强制休眠中";
            detailStr = `剩余约 ${remainingMin} 分钟后恢复`;
        } else if (isRunning) {
            currentStatus = "推土扫荡中...";
            detailStr = "";
        } else {
            currentStatus = "待机就绪";
            detailStr = "";
        }

        // toast 风控检测（软风控）
        let toastText = document.querySelector('[data-testid="toast"]')?.innerText || "";
        if (toastText.includes("速度限制") || toastText.includes("limit")) {
            currentStatus = "风控强制休眠中";
        }
        
        let currentAdded = getAccountStats().follows_today || 0;
        
        // 通过 background.js 上报（避免 HTTPS 页面的 Mixed Content 问题）
        // 把本地累计统计纳入 stats，每次心跳同步到 NAS
        try {
            chrome.runtime.sendMessage({
                action: "send_report",
                payload: {
                    worker_id: workerId,
                    engine: "follow",
                    status: currentStatus,
                    detail: detailStr,
                    stats: {
                        added: currentAdded
                    }
                }
            }, (response) => {
                if (chrome.runtime.lastError) {
                    console.log('[心跳] Service Worker 未就绪');
                }
            });
        } catch(e) {}
    }, 5000); // 5秒心跳

    // V11.12.7: follow 预占位，轮询启动直到成功或被跳过
    sessionStorage.setItem("matrix_tab_role", "follow_pending");
    var followBootAttempts = 0;
    (function tryBootFollow() {
        setTimeout(function() {
            if (isRunning) return;
            if (isAnotherTabRunning()) {
                sessionStorage.setItem("matrix_tab_role", "follow_skipped");
                return;
            }
            followBootAttempts++;
            // 检查页面是否加载完 (DOM 有足够节点)
            if (!document.querySelector('article') && !document.querySelector('[data-testid=\"primaryColumn\"]') && followBootAttempts < 10) {
                tryBootFollow();
                return;
            }
            sessionStorage.setItem("matrix_tab_role", "follow");
            isRunning = true;
            localStorage.setItem("matrix_step", "FETCH");
            sessionStorage.setItem("matrix_tab_running", "true");
            runEngine();
        }, 3000);
    })();

})();
