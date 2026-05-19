// X-Matrix-Bot 插件版 - 私信聊天 (V11.5.3 比特浏览器兼容版+直接请求备用)
(function() {
    'use strict';

    // ==============================================================================
    // 【无图防爆模式】
    // ==============================================================================
    const mediaBlocker = document.createElement('style');
    mediaBlocker.id = 'matrix-media-blocker';
    mediaBlocker.innerHTML = `
        img, video, svg, [data-testid="tweetPhoto"], [data-testid="videoPlayer"], [data-testid="videoComponent"] {
            opacity: 0 !important; visibility: hidden !important; pointer-events: none !important;
        }
        .css-1dbjc4n[style*="background-image"] { background-image: none !important; }
    `;
    let isHideImg = localStorage.getItem('matrix_hide_images') !== 'false';
    if (isHideImg) document.head.appendChild(mediaBlocker);

    // ==============================================================================
    // 【全局配置与存储引擎】
    // ==============================================================================
    // NAS地址已从config.js统一管理，此处不再硬编码


    // ================= 【实例唯一标识 - 解决多开冲突】 =================
    let instanceId = sessionStorage.getItem('matrix_instance_id');
    if (!instanceId) {
        instanceId = Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem('matrix_instance_id', instanceId);
    }

    // 立即建立端口连接唤醒 Service Worker
    (function wakeSW() {
        try {
            const p = chrome.runtime.connect({ name: 'chat_wake' });
            p.postMessage({ action: 'ping' });
            setTimeout(() => { try { p.disconnect(); } catch(e) {} }, 1000);
        } catch(e) {}
    })();

    // ================= 【诊断日志】 =================
    console.log('[诊断-注入] content_chat.js 已加载');
    console.log('[诊断-环境] chrome 对象:', typeof chrome);
    console.log('[诊断-环境] chrome.runtime:', typeof chrome !== 'undefined' ? typeof chrome.runtime : 'N/A');
    console.log('[诊断-环境] chrome.runtime.sendMessage:', typeof chrome !== 'undefined' && chrome.runtime ? typeof chrome.runtime.sendMessage : 'N/A');

    const GM_getValue = (key, def) => { let val = localStorage.getItem(key); return val !== null ? val : (def !== undefined ? def : null); };
    const GM_setValue = (key, val) => { localStorage.setItem(key, val); };

    function updateLocalStats(actionType) {
        // 兼容旧数据：把旧的 ignored 迁移到 corpse
        let raw = GM_getValue('matrix_local_stats', '');
        let stats;
        if (raw) {
            stats = JSON.parse(raw);
            if (stats.ignored !== undefined && stats.corpse === undefined) {
                stats.corpse = stats.ignored;
                stats.reject = 0;
                delete stats.ignored;
            }
        } else {
            stats = {ice:0, ad:0, corpse:0, reject:0, start_time:0};
        }
        if (stats.start_time === 0) stats.start_time = Date.now();
        if (actionType === 'ICEBREAKER') stats.ice++;
        if (actionType === 'AD') stats.ad++;
        if (actionType === 'IGNORED' || actionType === 'CORPSE') stats.corpse++;
        if (actionType === 'REJECT') stats.reject++;
        GM_setValue('matrix_local_stats', JSON.stringify(stats));
        renderStats();
    }

    function renderStats() {
        let raw = GM_getValue('matrix_local_stats', '');
        let stats = raw ? JSON.parse(raw) : {ice:0, ad:0, corpse:0, reject:0, start_time:0};
        // 兼容旧数据
        if (stats.ignored !== undefined && stats.corpse === undefined) {
            stats.corpse = stats.ignored; stats.reject = 0;
        }
        let days = stats.start_time > 0 ? Math.max(1, Math.ceil((Date.now() - stats.start_time) / (1000 * 60 * 60 * 24))) : 1;
        let poolStats = document.getElementById('matrix-pool-stats');
        if (poolStats) poolStats.innerText = `运行第${days}天 | 破冰:${stats.ice||0} | 广告:${stats.ad||0} | 尸体:${stats.corpse||0} | 拉黑:${stats.reject||0}`;
    }

    // 获取带实例标识的 worker_id
    function getWorkerId() {
        let workerId = sessionStorage.getItem('matrix_worker_id');
        if (!workerId || workerId.includes('null') || workerId.includes('undefined')) {
            let myHandleEl = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]');
            let myHandle = (myHandleEl && myHandleEl.href) ? myHandleEl.href.split('/').pop() : null;
            if (!myHandle || myHandle === 'null') {
                myHandle = "突击手_" + Math.floor(Math.random() * 90000 + 10000);
            }
            workerId = "@" + myHandle + "#" + instanceId;
            sessionStorage.setItem('matrix_worker_id', workerId);
        }
        return workerId;
    }


    function getCurrentTaskPayload() {
        try { return JSON.parse(localStorage.getItem('matrix_current_task') || 'null'); }
        catch (e) { return null; }
    }

    function getCurrentActionIndex() {
        let raw = localStorage.getItem('matrix_action_index');
        let parsed = parseInt(raw || '0', 10);
        return isNaN(parsed) ? 0 : parsed;
    }

    function callBackground(action, payload) {
        return new Promise((resolve, reject) => {
            try {
                chrome.runtime.sendMessage({ action: action, payload: payload || {} }, function(response) {
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
        let resp = await callBackground('guard_next_action', {});
        return resp && resp.status === 'success' ? resp.data : null;
    }

    async function guardCompleteAction(actionName, details) {
        let resp = await callBackground('guard_complete_action', {
            action: actionName,
            success: true,
            details: details || {}
        });
        return resp && resp.status === 'success' ? resp.data : null;
    }

    async function guardFailAction(actionName, details) {
        let resp = await callBackground('guard_fail_action', {
            action: actionName,
            error_code: (details && details.error_code) || 'action_failed',
            error_message: (details && details.error_message) || '',
            details: details || {}
        });
        return resp && resp.status === 'success' ? resp.data : null;
    }

    function resolveActionIndex(currentTask, actionType) {
        if (!currentTask || !Array.isArray(currentTask.action_plan)) return null;
        var normalized = String(actionType || '').trim().toLowerCase();
        var nameMap = { icebreaker: 'icebreaker', ad: 'ad', chat: 'chat', reject: 'chat', ignored: 'chat', corpse: 'chat' };
        var expected = nameMap[normalized];
        if (!expected) return null;
        for (var i = 0; i < currentTask.action_plan.length; i++) {
            var item = currentTask.action_plan[i];
            if (!item || typeof item !== 'object') continue;
            if (String(item.name || '').trim().toLowerCase() === expected) return i;
            if (String(item.action || '').trim().toLowerCase() === expected) return i;
        }
        return null;
    }

    function getPlannedActionNames(currentTask) {
        if (!currentTask || !Array.isArray(currentTask.action_plan)) return [];
        return currentTask.action_plan
            .filter(function(item) { return item && typeof item === 'object'; })
            .map(function(item) { return String(item.name || item.action || '').trim().toLowerCase(); })
            .filter(function(name) { return name.length > 0; });
    }

    function isTaskActionAllowed(actionName) {
        var currentTask = getCurrentTaskPayload();
        var plannedNames = getPlannedActionNames(currentTask);
        if (!plannedNames.length) return true;
        return plannedNames.indexOf(String(actionName || '').trim().toLowerCase()) >= 0;
    }

    // 战报上报格式对接 V11.4 后端大屏（通过 background.js 避免 Mixed Content）
    function sendLogToNAS(targetHandle, actionType, detailMsg = '', extra = {}) {
        updateLocalStats(actionType);
        let botId = getWorkerId();
        let currentTask = getCurrentTaskPayload();
        let payload = {
            bot_id: botId,
            target: targetHandle,
            action_type: actionType,
            detail: detailMsg
        };
        if (currentTask) {
            payload.task_id = currentTask.task_id || null;
            payload.action_plan = Array.isArray(currentTask.action_plan) ? currentTask.action_plan : [];
            payload.action_index = getCurrentActionIndex();
            payload.target_handle = targetHandle;
        }
        payload = Object.assign(payload, extra || {});
        
        function trySend(attemptsLeft) {
            try {
                chrome.runtime.sendMessage({
                    action: "log_action",
                    payload: payload
                }, (response) => {
                    if (chrome.runtime.lastError) {
                        console.log('[战报] Service Worker 未就绪');
                        return;
                    }
                    if (!response || response.status !== "success") {
                        console.warn('[战报] 上报失败:', response);
                        if (attemptsLeft > 0) {
                            setTimeout(() => trySend(attemptsLeft - 1), 2000);
                        }
                    } else {
                        console.log('[战报] 上报成功:', actionType);
                    }
                });
            } catch(e) {
                console.error('[战报] 发送异常:', e);
                if (attemptsLeft > 0) {
                    setTimeout(() => trySend(attemptsLeft - 1), 2000);
                }
            }
        }
        
        trySend(2); // 最多重试2次
    }

    // ==============================================================================
    // 【原生插件版 活水链接拉取引擎】
    // ==============================================================================
    let current_live_links = [];  // 空数组表示未初始化，禁止发送广告

    async function fetchLiveLinks() {
        return new Promise((resolve) => {
            try {
                console.log('[活水] 正在获取链接...');
                
                // 必须通过 background.js 代理请求（x.com CSP 禁止页面内直接访问外部 HTTP）
                if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
                    chrome.runtime.sendMessage(
                        { action: "fetch_links" },
                        (response) => {
                            if (chrome.runtime.lastError) {
                                console.error('[活水] background.js 通信失败:', chrome.runtime.lastError.message);
                                console.log('[活水] 将在下次定时轮询时重试');
                                resolve(false);
                                return;
                            }
                            
                            if (response && response.status === "success" && response.data) {
                                processLinksText(response.data, resolve);
                            } else {
                                console.error('[活水] background.js 返回错误:', response);
                                resolve(false);
                            }
                        }
                    );
                } else {
                    console.error('[活水] chrome.runtime 不可用！扩展环境异常，无法获取链接');
                    resolve(false);
                }
            } catch (error) { 
                console.error('[活水] 获取异常:', error);
                resolve(false);
            }
        });
    }
    
    // 处理链接文本
    function processLinksText(text, resolve) {
        console.log('[活水] 原始响应:', text.substring(0, 100));
        
        // 🚨 安全校验：拒绝错误响应和兜底链接
        if (text.includes('ERROR_NO_LINKS_CONFIGURED') || text.includes('@default') || text.includes('@兜底')) {
            console.error('[活水] 🚨 服务器返回错误/兜底链接，拒绝使用！');
            resolve(false);
            return;
        }
        
        let lines = text.split('\n').map(l => l.trim()).filter(l => l.startsWith('http'));
        console.log('[活水] 解析后链接数:', lines.length);
        if (lines.length > 0) {
            current_live_links = lines;
            console.log('[活水] ✅ 链接已更新:', current_live_links);
            // 更新 UI
            updateLinksUI();
            resolve(true);
        } else {
            console.log('[活水] 没有有效链接，保持当前:', current_live_links);
            resolve(false);
        }
    }
    
    // 更新链接显示UI
    function updateLinksUI() {
        let linksInput = document.getElementById('matrix-links-input');
        if (linksInput && current_live_links.length > 0) { 
            linksInput.value = current_live_links.join('\n'); 
            linksInput.style.borderColor = "#00ba7c"; 
            setTimeout(() => { if(linksInput) linksInput.style.borderColor = "#cfd9de"; }, 1000); 
            console.log('[活水] UI已更新，显示', current_live_links.length, '个链接');
        } else if (linksInput) {
            linksInput.value = '';
            console.log('[活水] UI已清空');
        } else {
            console.log('[活水] UI元素未找到，稍后重试更新...');
            setTimeout(updateLinksUI, 1000);
        }
    }
    fetchLiveLinks();
    setInterval(fetchLiveLinks, 180000); // 3分钟刷新一次活水

    function getLiveLink() {
        if (!current_live_links || current_live_links.length === 0) {
            console.error('[活水] 🚨 没有可用链接！广告发送被阻止。');
            return null;  // 返回null表示禁止发送
        }
        return current_live_links[Math.floor(Math.random() * current_live_links.length)];
    }

    // ==============================================================================
    // 【核心配置与判定 DNA】
    // ==============================================================================
    const ICEBREAKER_MESSAGE = "いきなりごめんなさい💦\n同世代より、大人の余裕がある人がいいなーって探してて、メッセージしちゃいました🫣\nちなみに、今おいくつですか？👀";
    const AD_MESSAGE_TEMPLATE = "お返事ありがとう💕 やっぱり大人の余裕があって素敵ですね！\n其实は、お互い気が合えばデートとかもしてみたいなって思ってるんですけど…\nここだとすぐ制限かかってメッセージ消されちゃうみたいで😭💦\n\n相談だけでも、こっちの秘密のアカウントでしませんか？🫣\n👇\n{LINK}\n\nこっちならすぐ気づけるので、追加したらスタンプ送っておいてね💋";
    const KICK_MESSAGE = "ごめんなさい💦 こっちだとメッセージ見落としちゃいそうで…😭 さっきのURLからこっそり連絡もらえるとすごく嬉しいな🥺 待ってます💕";
    const REJECT_MESSAGE = "ごめんね😭 24歳以上で探してて💦 また機会があれば！";
    const FOREIGNER_REJECT_MESSAGE = "Sorry, I only speak Japanese 💦 ごめんなさい、日本語しか分からないです😭";

    // ========== 【DNA 关键词：分高权重核心词和低权重辅助词】 ==========
    // 核心词：几乎不可能在对方消息中出现，单条命中即判定为"我发的"
    const MY_DNA_CORE = [
        "line.me", "http", "秘密のアカウント", "👇",
        "デートとかもしてみたいな", "24歳以上で探してて",
        "年上の方が好みで", "日本語しか分からないです"
    ];
    // 辅助词：通用日语表达，需要至少2条同时出现才判定（减少误判）
    const MY_DNA_AUX = [
        "いきなりごめんなさい", "今おいくつですか", "いきなりでごめんね", "年齢だけ聞いてもいいですか",
        "見落としちゃう", "見落としちゃいそうで", "待ってます"
    ];
    const MAX_DB_SIZE = 8000;

    function getDB(key) { return new Set(JSON.parse(GM_getValue(key, '[]')).map(id => id.replace(/^\//, '').toLowerCase())); }

    function saveToDB(key, id) {
        let dbArr = Array.from(getDB(key));
        let cleanId = id.replace(/^\//, '').toLowerCase();
        if (!dbArr.includes(cleanId)) {
            dbArr.push(cleanId);
            if (dbArr.length > MAX_DB_SIZE) dbArr = dbArr.slice(500); 
            GM_setValue(key, JSON.stringify(dbArr)); 
        }
    }

    function getSessionList() { return JSON.parse(sessionStorage.getItem('matrix_session_scanned') || '[]'); }
    function addSessionList(url) {
        let arr = getSessionList();
        if(!arr.includes(url)) arr.push(url);
        sessionStorage.setItem('matrix_session_scanned', JSON.stringify(arr));
    }

    // ========== 【消息时间检测：判断最后一条消息距离现在多少天】 ==========
    function getLatestMessageAgeDays() {
        const timeEls = document.querySelectorAll('time[datetime]');
        let latestDate = null;
        
        for (let el of timeEls) {
            let dt = el.getAttribute('datetime');
            if (dt) {
                let d = new Date(dt);
                if (!isNaN(d.getTime()) && (!latestDate || d > latestDate)) {
                    latestDate = d;
                }
            }
        }
        
        if (latestDate) {
            let now = new Date();
            let today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            let msgDay = new Date(latestDate.getFullYear(), latestDate.getMonth(), latestDate.getDate());
            let diffDays = Math.floor((today - msgDay) / (1000 * 60 * 60 * 24));
            return diffDays; // 0=今天, 1=昨天, 2=前天...
        }
        
        // 如果找不到 datetime，通过页面文本推断
        const bodyText = document.body.innerText;
        // 页面中出现了月份格式的日期（如 "May 1"），说明有旧消息
        const monthDatePattern = /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}/i;
        if (monthDatePattern.test(bodyText)) {
            // 保守估计：出现月份日期格式，至少前天
            let match = bodyText.match(monthDatePattern);
            if (match) {
                let monthNames = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
                let msgMonth = monthNames.indexOf(match[1].toLowerCase());
                let msgDay = parseInt(match[2]);
                let now = new Date();
                let today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                // 尝试推断年份（假设是今年）
                let msgDate = new Date(now.getFullYear(), msgMonth, msgDay);
                let diffDays = Math.floor((today - msgDate) / (1000 * 60 * 60 * 24));
                if (diffDays >= 0) return diffDays;
                // 如果计算出负数，可能是去年的日期
                msgDate = new Date(now.getFullYear() - 1, msgMonth, msgDay);
                diffDays = Math.floor((today - msgDate) / (1000 * 60 * 60 * 24));
                return Math.max(diffDays, 30); // 至少30天
            }
            return 2; // 兜底：至少前天
        }
        
        return 0; // 无法判断，默认是新消息
    }

    // ========== 【UI 面板注入】 ==========
    const style = document.createElement('style');
    style.innerHTML = `
        #matrix-switch-btn { position: fixed; bottom: 20px; left: 20px; background-color: #f91880; color: white; border: none; border-radius: 50%; width: 50px; height: 50px; padding: 0; font-size: 24px; cursor: pointer; z-index: 999999; box-shadow: 0 4px 15px rgba(249,24,128,0.4); transition: 0.3s; display: flex; align-items: center; justify-content: center; }
        #matrix-switch-btn.running { background-color: #888888 !important; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important; filter: none !important; opacity: 1 !important; }
        #matrix-switch-btn.auto-mode { background-color: #00ba7c !important; box-shadow: 0 4px 15px rgba(0,186,124,0.4) !important; }
        #matrix-settings-btn { position: fixed; bottom: 80px; left: 25px; background-color: #444; color: white; border: none; border-radius: 50%; width: 40px; height: 40px; font-size: 18px; cursor: pointer; z-index: 999999; box-shadow: 0 4px 10px rgba(0,0,0,0.3); transition: 0.2s; }
        #matrix-config-panel { position: fixed; bottom: 130px; left: 20px; background: white; border: 1px solid #e1e8ed; padding: 15px; border-radius: 12px; z-index: 999999; display: none; box-shadow: 0 8px 20px rgba(0,0,0,0.15); width: 280px; font-family: sans-serif; }
        #matrix-config-panel h3 { margin: 0 0 10px 0; font-size: 15px; color: #0f1419; }
        .matrix-input-field { width: 100%; box-sizing: border-box; margin-bottom: 12px; font-family: monospace; font-size: 12px; padding: 8px; border: 1px solid #cfd9de; border-radius: 4px; outline: none; transition: border-color 0.3s; }
        #matrix-links-input { height: 80px; resize: vertical; }
        .matrix-action-btn { background: #0f1419; color: white; border: none; padding: 8px; border-radius: 6px; cursor: pointer; width: 48%; font-weight: bold; font-size: 12px; }
        .matrix-btn-group { display: flex; justify-content: space-between; }
        .matrix-stats { font-size: 12px; opacity: 0.9; color: #1d9bf0; margin-top: 10px; font-weight: bold; text-align: center; background:#f0f3f4; padding:5px; border-radius:4px;}
        #auto-dm-toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #1d9bf0; color: white; padding: 12px 24px; border-radius: 8px; font-size: 16px; font-weight: bold; z-index: 999999; display: none; pointer-events: none; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
    `;
    document.head.appendChild(style);

    const toast = document.createElement('div');
    toast.id = 'auto-dm-toast'; document.body.appendChild(toast);
    function showToast(msg, color = '#1d9bf0', time = 2500) {
        toast.innerText = msg; toast.style.background = color; toast.style.display = 'block';
        setTimeout(() => { toast.style.display = 'none'; }, time);
    }

    const masterBtn = document.createElement('button');
    masterBtn.id = 'matrix-switch-btn'; masterBtn.innerText = '🚀'; document.body.appendChild(masterBtn);
    const settingsBtn = document.createElement('button');
    settingsBtn.id = 'matrix-settings-btn'; settingsBtn.innerText = '⚙️'; document.body.appendChild(settingsBtn);

    const configPanel = document.createElement('div');
    configPanel.id = 'matrix-config-panel';
    configPanel.innerHTML = `
        <h3><span>🔗 控制面板</span></h3>
        <textarea id="matrix-links-input" class="matrix-input-field" placeholder="NAS 自动下发，无需手动填写" readonly></textarea>
        <div class="matrix-btn-group">
            <button id="matrix-save-btn" class="matrix-action-btn">手动刷新</button>
            <button id="matrix-check-db-btn" class="matrix-action-btn" style="background:#ff4d4f">📦 查黑名单</button>
        </div>
        <div class="matrix-btn-group" style="margin-top: 10px;">
            <button id="matrix-toggle-img-btn" class="matrix-action-btn" style="background:#1d9bf0; width:100%;"></button>
        </div>
        <div class="matrix-btn-group" style="margin-top: 10px;">
            <label style="display:flex; align-items:center; gap:6px; font-size:12px; color:#0f1419; cursor:pointer; width:100%; justify-content:center; padding:6px; border:1px solid #cfd9de; border-radius:6px; background:#f7f9f9;">
                <input type="checkbox" id="matrix-auto-start-checkbox" style="cursor:pointer;">
                <span>🤖 页面打开时自动启动</span>
            </label>
        </div>
        <div class="matrix-stats" id="matrix-pool-stats">本地数据已锁定保护</div>
    `;
    document.body.appendChild(configPanel);

    const linksInput = document.getElementById('matrix-links-input');
    const saveBtn = document.getElementById('matrix-save-btn');
    const checkDbBtn = document.getElementById('matrix-check-db-btn');
    const toggleImgBtn = document.getElementById('matrix-toggle-img-btn');

    toggleImgBtn.innerText = isHideImg ? '🖼️ 无图防爆: [开启]' : '🖼️ 无图防爆: [关闭]';

    toggleImgBtn.onclick = () => {
        isHideImg = !isHideImg;
        localStorage.setItem('matrix_hide_images', isHideImg);
        toggleImgBtn.innerText = isHideImg ? '🖼️ 无图防爆: [开启]' : '🖼️ 无图防爆: [关闭]';
        if (isHideImg) { document.head.appendChild(mediaBlocker); showToast('✅ 已隐藏图片 (省内存)', '#1d9bf0'); } 
        else { let el = document.getElementById('matrix-media-blocker'); if (el) el.remove(); showToast('✅ 已显示图片', '#1d9bf0'); }
    };

    settingsBtn.onclick = () => {
        if (configPanel.style.display === 'none' || configPanel.style.display === '') {
            configPanel.style.display = 'block'; linksInput.value = current_live_links.join('\n'); renderStats(); fetchLiveLinks();
        } else { configPanel.style.display = 'none'; }
    };

    saveBtn.onclick = () => {
        fetchLiveLinks();
        showToast('✅ 正在向 NAS 申请最新活水链接', '#1d9bf0', 2000);
    };

    checkDbBtn.onclick = () => { alert(`✅ 本地黑名单安全！\n总计已永久拉黑： ${Array.from(getDB('reject_sent_users')).length} 人`); };

    // ================= 【自动/手动启动模式切换】 =================
    const AUTO_START_KEY = 'matrix_chat_auto_start_enabled';

    function isAutoStartEnabled() {
        return localStorage.getItem(AUTO_START_KEY) === 'true';
    }

    function setAutoStartEnabled(enabled) {
        localStorage.setItem(AUTO_START_KEY, enabled ? 'true' : 'false');
    }

    function updateMasterBtn() {
        if (sessionStorage.getItem('matrix_auto_run') === 'true') {
            masterBtn.title = '引擎运行中 (点击停止)';
            masterBtn.className = 'running';
            masterBtn.innerText = '⏹';
        } else {
            masterBtn.title = isAutoStartEnabled() ? '自动启动模式 (点击手动启动)' : '手动启动模式 (点击启动)';
            masterBtn.className = isAutoStartEnabled() ? 'auto-mode' : '';
            masterBtn.innerText = isAutoStartEnabled() ? '🤖' : '🚀';
        }
    }

    // 初始化设置面板中的自动启动复选框
    const autoStartCheckbox = document.getElementById('matrix-auto-start-checkbox');
    if (autoStartCheckbox) {
        autoStartCheckbox.checked = isAutoStartEnabled();
        autoStartCheckbox.addEventListener('change', (e) => {
            const enabled = e.target.checked;
            setAutoStartEnabled(enabled);
            showToast(enabled ? '🤖 自动启动已开启！下次打开页面将自动运行' : '🔒 自动启动已关闭', enabled ? '#00ba7c' : '#f91880', 2000);
            updateMasterBtn();
        });
    }

    // 获取当前登录用户的 handle
    function getMyHandle() {
        let myHandleEl = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]');
        if (myHandleEl && myHandleEl.href) {
            return myHandleEl.href.split('/').pop().toLowerCase();
        }
        // 从 worker_id 缓存获取
        let workerId = sessionStorage.getItem('matrix_worker_id');
        if (workerId) {
            return workerId.split('#')[0].replace('@', '').toLowerCase();
        }
        return null;
    }

    // 检查是否在自己的 followers 页面（私信脚本专属）
    function isMyFollowersPage() {
        if (!window.location.pathname.includes('/followers')) return false;
        let pathHandle = window.location.pathname.split('/')[1].toLowerCase();
        let myHandle = getMyHandle();
        if (!myHandle) {
            // 无法确定，默认不启动（避免在错误的页面启动）
            console.log('[隔离] 无法确定当前用户，跳过自动启动');
            return false;
        }
        return pathHandle === myHandle;
    }

    function tryAutoStart() {
        // 自动启动条件检查
        if (!isAutoStartEnabled()) return false;
        if (sessionStorage.getItem('matrix_auto_run') === 'true') return false;
        // NAS 下发模式：从任何页面均可启动
        if (!isMyFollowersPage()) {
            console.log('[自动启动] NAS 下发模式');
        }
        // 活水链接通过 NAS 下发
        if (!current_live_links || current_live_links.length === 0) {
            console.log('[自动启动] 引流链接未就绪, 等待 NAS 下发');
        }

        console.log('[自动启动] 私信引擎自动启动中...');
        sessionStorage.setItem('matrix_auto_run', 'true');
        sessionStorage.removeItem('matrix_auto_step');
        sessionStorage.setItem('matrix_session_scanned', '[]');
        sessionStorage.setItem('matrix_warmup_timer', (Date.now() + 1000).toString());
        sessionStorage.setItem('matrix_target_username', window.location.pathname.split('/')[1]);
        showToast('🤖 私信引擎自动启动！', '#00ba7c', 2000);
        renderStats();
        updateMasterBtn();
        return true;
    }

    masterBtn.onclick = () => {
        if (sessionStorage.getItem('matrix_auto_run') === 'true') {
            // 停止引擎
            sessionStorage.setItem('matrix_auto_run', 'false');
            sessionStorage.removeItem('matrix_auto_step');
            showToast('🛑 引擎已停止', '#f91880');
        } else {
            // 启动引擎（手动）
            // 检查活水链接是否有效
            if (!current_live_links || current_live_links.length === 0) { 
                alert('⚠️ NAS尚未下发引流链接！请检查服务器。'); 
                return; 
            }
            // 【Tab 隔离】只在自己的 followers 页面启动
            if (!isMyFollowersPage()) { showToast('⚠️ 必须在【自己的关注者列表】页面启动！', '#f91880', 3000); return; }
            
            sessionStorage.setItem('matrix_auto_run', 'true');
            sessionStorage.removeItem('matrix_auto_step');
            sessionStorage.setItem('matrix_session_scanned', '[]');
            sessionStorage.setItem('matrix_warmup_timer', (Date.now() + 1000).toString());
            sessionStorage.setItem('matrix_target_username', window.location.pathname.split('/')[1]);
            showToast(`🚀 引擎启动！`, '#1d9bf0', 2000);
            renderStats();
        }
        updateMasterBtn();
    };

    updateMasterBtn();
    renderStats();

    // 页面加载后尝试自动启动（等待活水链接加载完成）
    async function initAutoStart() {
        // 先等待活水链接加载（最多重试3次）
        let retryCount = 0;
        const maxRetries = 3;
        
        while (retryCount < maxRetries) {
            const success = await fetchLiveLinks();
            if (success && current_live_links.length > 0) {
                console.log('[初始化] ✅ 活水链接已就绪:', current_live_links);
                break;
            }
            
            retryCount++;
            if (retryCount < maxRetries) {
                console.log(`[初始化] 活水链接未就绪，第${retryCount}次重试...`);
                await new Promise(r => setTimeout(r, 3000));
            }
        }
        
        if (current_live_links.length === 0) {
            console.error('[初始化] 🚨 活水链接获取失败，广告功能已禁用');
        }
        
        // V11.10: fetch task from bridge
        try {
            // sendMessage 获取任务 (自动唤醒 SW)
            chrome.runtime.sendMessage(
                { action: 'fetch_task', script_name: 'chat', plugin_name: 'content_chat.js' },
                async function(response) {
                    if (chrome.runtime.lastError) return;
                    if (response && response.status === 'success' && response.task) {
                        var task = response.task;
                        localStorage.setItem('matrix_current_task', JSON.stringify(task));
                        localStorage.setItem('matrix_current_task_id', task.task_id || '');
                        localStorage.setItem('matrix_current_action_plan', JSON.stringify(task.action_plan || []));
                        localStorage.setItem('matrix_current_target_payload', JSON.stringify(task.target || {}));
                        localStorage.setItem('matrix_current_copy_payload', JSON.stringify(task.copy_payload || null));
                        var creator = (task.target && task.target.handle) || '';
                        localStorage.setItem('matrix_current_creator', String(creator).trim().replace('@','').toLowerCase());
                        try {
                            var next = await guardNextAction();
                            if (next && typeof next.action_index !== 'undefined') {
                                localStorage.setItem('matrix_action_index', String(next.action_index || 0));
                            }
                        } catch(e) {}
                    }
                }
            );
        } catch(e) {}
        
        // V11.12.7: 等 follow 决定，轮询启动，直到角色明确
        var chatBootAttempts = 0;
        (function tryBootChat() {
            setTimeout(function() {
                var role = sessionStorage.getItem("matrix_tab_role");
                // 还在 pending，follow 没决定 → 继续等
                if (role === "follow_pending" && chatBootAttempts < 10) {
                    chatBootAttempts++;
                    tryBootChat();
                    return;
                }
                // follow 没占这个 tab → chat 启动
                if (!role || role === "follow_skipped" || role === "chat") {
                    if (role !== "chat") sessionStorage.setItem("matrix_tab_role", "chat");
                    localStorage.setItem(AUTO_START_KEY, 'true');
                    tryAutoStart();
                }
            }, 5000);
        })();
    }
    
    
    // 远程启动/停止引擎信号
    chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
        if (request.action === 'start_engine') {
            // 只响应 chat 引擎命令，follow 引擎命令跳过
            var cmdScript = request.payload && request.payload.script_name;
            if (cmdScript && cmdScript !== 'chat') return;
            if (request.payload && request.payload.task_id) {
                localStorage.setItem('matrix_current_task', JSON.stringify({
                    task_id: request.payload.task_id || '',
                    script_name: request.payload.script_name || 'chat',
                    action_plan: request.payload.action_plan || [],
                    target: request.payload.target || {},
                    copy_payload: request.payload.copy_payload || null,
                }));
                localStorage.setItem('matrix_current_task_id', request.payload.task_id || '');
                localStorage.setItem('matrix_current_action_plan', JSON.stringify(request.payload.action_plan || []));
                localStorage.setItem('matrix_current_target_payload', JSON.stringify(request.payload.target || {}));
                localStorage.setItem('matrix_current_copy_payload', JSON.stringify(request.payload.copy_payload || null));
            }
            if (sessionStorage.getItem('matrix_auto_run') !== 'true') {
                sessionStorage.setItem('matrix_auto_run', 'true');
                sessionStorage.removeItem('matrix_auto_step');
                sessionStorage.setItem('matrix_session_scanned', '[]');
                sessionStorage.setItem('matrix_warmup_timer', (Date.now() + 1000).toString());
                showToast('\u6e20道引擎启动！', '#1d9bf0', 2000);
                renderStats();
                updateMasterBtn();
                sendResponse({ status: 'started' });
                return true;
            }
        }
        if (request.action === 'stop_engine') {
            if (sessionStorage.getItem('matrix_auto_run') === 'true') {
                sessionStorage.setItem('matrix_auto_run', 'false');
                sessionStorage.removeItem('matrix_auto_step');
                showToast('\u6e20道引擎停止', '#f91880', 2000);
                renderStats();
                updateMasterBtn();
                sendResponse({ status: 'stopped' });
            }
        }
    });

    // 延迟启动，确保页面和链接都就绪
    setTimeout(initAutoStart, 2500);
    
    // ========== 【批量同步本地累计统计到 NAS】 ==========
    setTimeout(() => {
        let localStats = JSON.parse(GM_getValue('matrix_local_stats', '{"ice":0, "ad":0, "ignored":0}'));
        let botId = getWorkerId();
        let total = (localStats.ice || 0) + (localStats.ad || 0) + (localStats.ignored || 0);
        if (total > 0) {
            console.log(`[批量同步] 本地累计: 破冰${localStats.ice} 广告${localStats.ad} 拦截${localStats.ignored}，正在上传到 NAS...`);
            try {
                chrome.runtime.sendMessage({
                    action: "send_report",
                    payload: {
                        worker_id: botId,
                        engine: "chat",
                        status: "批量同步本地统计",
                        detail: `破冰${localStats.ice} 广告${localStats.ad} 拦截${localStats.ignored}`,
                        stats: {
                            ice: localStats.ice || 0,
                            ad: localStats.ad || 0,
                            ignored: localStats.ignored || 0
                        }
                    }
                }, (response) => {
                    if (chrome.runtime.lastError) {
                        console.error('[批量同步] Service Worker 未就绪');
                    } else if (response && response.status === 'success') {
                        console.log('[批量同步] ✅ 上传成功！大屏将显示正确累计值');
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
    // 寻框与打字函数
    // ==============================================================================
    function findBottomAwakeningTarget() {
        const targets = document.querySelectorAll(`[contenteditable="true"], [data-testid*="dmComposerTextInput"], [role="textbox"], [role="combobox"], [aria-label*="Message" i], [aria-label*="消息"], [placeholder*="Message" i], [placeholder*="消息"]`);
        let validTargets = Array.from(targets).filter(el => { const rect = el.getBoundingClientRect(); return rect.width > 0 && rect.height > 0 && rect.top > 0; });
        if (validTargets.length > 0) { validTargets.sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top); return validTargets[0]; }
        return null;
    }

    function threadSafeSend(inputElement, text) {
        inputElement.click(); inputElement.focus();
        const sel = window.getSelection(); const range = document.createRange();
        range.selectNodeContents(inputElement); range.collapse(false);
        sel.removeAllRanges(); sel.addRange(range);
        let success = document.execCommand('insertText', false, text);
        if (!success) { inputElement.textContent = text; inputElement.dispatchEvent(new Event('input', { bubbles: true, cancelable: true })); }
        setTimeout(() => {
            const sendBtn = document.querySelector('[data-testid="dmComposerSendButton"]');
            if (sendBtn && !sendBtn.disabled) sendBtn.click();
            else inputElement.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, cancelable: true, keyCode: 13, key: 'Enter' }));
        }, 1500); 
    }

    // ==============================================================================
    // 核心判断：DNA 判定
    // ==============================================================================
    function getChatDecision(targetHandle) {
        let rejectDB = getDB('reject_sent_users');
        if (rejectDB.has(targetHandle)) return { action: 'SKIP_REJECTED' };

        const mainArea = document.querySelector('main');
        if (!mainArea) return { action: 'STILL_LOADING' };

        let textEls = Array.from(mainArea.querySelectorAll('[dir="auto"], [data-testid="tweetText"]')).filter(el => {
            let txt = el.innerText ? el.innerText.trim() : '';
            if (!txt || /^\s*(上午|下午|AM|PM)?\s*\d{1,2}:\d{2}\s*(AM|PM)?\s*$/i.test(txt)) return false;
            let hasChild = Array.from(el.querySelectorAll('[dir="auto"], [data-testid="tweetText"]')).length > 0;
            return !hasChild;
        });

        let validBubbles = [];
        let wrapperRect = mainArea.getBoundingClientRect();

        for (let el of textEls) {
            let rect = el.getBoundingClientRect();
            if (rect.top < wrapperRect.top + 30) continue;
            
            let text = el.innerText.trim();
            let rawTxt = text.replace(/\s+/g, '');
            
            // DNA 权重判定：核心词命中即判定为"我发的"；辅助词需至少2个命中
            let coreHit = MY_DNA_CORE.some(dna => rawTxt.includes(dna));
            let auxHits = MY_DNA_AUX.filter(dna => rawTxt.includes(dna)).length;
            let isMine = coreHit || auxHits >= 2;
            let owner = isMine ? 'MINE' : 'THEIRS';
            
            validBubbles.push({ text: text, top: rect.top, owner: owner });
        }

        if (validBubbles.length === 0) {
            let rawText = document.body.innerText.replace(/\s+/g, '');
            let hasAnyDNA = MY_DNA_CORE.some(dna => rawText.includes(dna)) || MY_DNA_AUX.some(dna => rawText.includes(dna));
            if (hasAnyDNA) {
                if (rawText.includes("見落としちゃう") || rawText.includes("容易看漏")) return { action: 'SKIP_MAXED' };
                if (rawText.includes("24歳以上") || rawText.includes("Japanese")) {
                    saveToDB('reject_sent_users', targetHandle); return { action: 'SKIP_REJECTED' };
                }
                return { action: 'SKIP_WAITING' };
            }
            let mainText = mainArea.innerText || '';
            let isLoaded = mainText.includes('@') && (mainText.includes('Joined') || mainText.includes('加入于') || mainText.includes('View Profile') || mainText.includes('查看个人资料') || mainText.includes('关注者'));
            if (!isLoaded) return { action: 'STILL_LOADING' };
            return { action: 'SEND_ICEBREAKER' };
        }

        validBubbles.sort((a, b) => a.top - b.top);
        let lastSenderOverall = validBubbles[validBubbles.length - 1].owner;
        let theirRecentText = ''; let myLastMessageText = '';

        if (lastSenderOverall === 'THEIRS') {
            let i = validBubbles.length - 1;
            while (i >= 0 && validBubbles[i].owner === 'THEIRS') { theirRecentText = validBubbles[i].text + " " + theirRecentText; i--; }
            while (i >= 0) { if (validBubbles[i].owner === 'MINE') myLastMessageText = validBubbles[i].text + " " + myLastMessageText; i--; }
        } else return { action: 'SKIP_WAITING' }; 

        if (lastSenderOverall === 'THEIRS') {
            let safeText = theirRecentText.replace(/\b\d{1,2}:\d{2}\b/g, ' ').replace(/[上|下]午\s*\d{1,2}:\d{2}/g, ' ');
            
            if (/http(s)?:\/\//i.test(safeText) || /line\.me/i.test(safeText) || /t\.co/i.test(safeText)) {
                saveToDB('reject_sent_users', targetHandle); return { action: 'SKIP_REJECTED' };
            }

            let hasJapanese = /[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\uFF66-\uFF9F]/.test(safeText);
            let hasAlphabet = /[a-zA-Z]/.test(safeText);
            let isPureEnglish = hasAlphabet && !hasJapanese;
            let lettersOnly = safeText.replace(/[^a-zA-Z]/g, '').toLowerCase();

            if (lettersOnly === 'ok' || lettersOnly === 'yes' || lettersOnly === 'no' || /^w+$/.test(lettersOnly)) isPureEnglish = false;
            if (isPureEnglish) { saveToDB('reject_sent_users', targetHandle); return { action: 'SEND_FOREIGNER_REJECT' }; }
            
            // ========== 【年龄检测 V2.5：三层判定】 ==========
            let ageMatch = null;
            // 层1：带年龄单位（18歳/19才/20sai）→ 直接命中
            ageMatch = safeText.match(/(?:^|[^\d])(1[0-9]|2[0-3])\s*(歳|才|岁|sai|years?)/i);
            // 层2：纯数字回复（对方只回"17""18"）→ 直接命中
            if (!ageMatch) {
                let cleanText = safeText.replace(/[\s\n\r\u200B-\u200D\uFEFF]/g, '');
                let pureNum = cleanText.match(/^\d{2}$/);
                if (pureNum) {
                    let num = parseInt(pureNum[0]);
                    if (num >= 10 && num <= 23) ageMatch = pureNum;
                }
            }
            // 层3：数字周围有年龄上下文
            if (!ageMatch) {
                let numMatch = safeText.match(/(?:^|[^\d])(1[0-9]|2[0-3])(?:[^\d]|$)/);
                if (numMatch) {
                    let idx = safeText.indexOf(numMatch[0]);
                    let context = safeText.substring(Math.max(0, idx - 10), Math.min(safeText.length, idx + 15));
                    if (/(歳|才|岁|sai|年|age|old|何|おいくつ|いくつ|くらい|だけ|年齢)/i.test(context)) {
                        ageMatch = numMatch;
                    }
                }
            }
            if (ageMatch) { saveToDB('reject_sent_users', targetHandle); return { action: 'SEND_REJECT' }; }
            
            if (!myLastMessageText) return { action: 'SEND_AD' };

            let myRaw = myLastMessageText.replace(/\s+/g, '');
            let iSentReject = myRaw.includes('24歳以上') || myRaw.includes('24岁以上') || myRaw.includes('年上') || myRaw.includes('日本語') || myRaw.includes('日语');
            
            let iSentKick = myRaw.includes('見落としちゃいそうで') || myRaw.includes('見落としちゃう') || myRaw.includes('待ってます') || myRaw.includes('容易看漏') || myRaw.includes('等你') || myRaw.includes('🥺');
            
            let iSentAd = myRaw.includes('line.me') || myRaw.includes('秘密のアカウント') || myRaw.includes('秘密账号') || myRaw.includes('👇');
            let iSentIcebreaker = myRaw.includes('いきなりごめんなさい') || myRaw.includes('大人の余裕') || myRaw.includes('突然打扰');

            if (iSentReject) { saveToDB('reject_sent_users', targetHandle); return { action: 'SKIP_REJECTED' }; }
            if (iSentKick) return { action: 'SKIP_MAXED' };
            if (iSentAd) return { action: 'SEND_KICK' };
            if (iSentIcebreaker) return { action: 'SEND_AD' };
            return { action: 'SEND_AD' };
        }
        return { action: 'SKIP_WAITING' };
    }

    // ========== 【主巡航引擎】 ==========
    let mainEngine = setInterval(() => {
        const isRunning = sessionStorage.getItem('matrix_auto_run') === 'true';
        if (!isRunning) return;

        let errorButtons = Array.from(document.querySelectorAll('button, div[role="button"]'));
        let retryBtn = errorButtons.find(btn => btn.innerText && (btn.innerText.includes('重试') || btn.innerText.includes('Retry') || btn.innerText.includes('限制')));
        if (retryBtn && window.location.href.includes('/followers')) { retryBtn.click(); }

        let lastHealthyTime = parseInt(sessionStorage.getItem('matrix_last_healthy_time') || Date.now().toString());
        let isHealthyDOM = document.querySelector('[data-testid="UserCell"]') || document.querySelector('[data-testid="dmComposerTextInput"]') || document.querySelector('[data-testid="sendDMFromProfile"]');

        if (isHealthyDOM) {
            sessionStorage.setItem('matrix_last_healthy_time', Date.now().toString());
        } else if (Date.now() - lastHealthyTime > 40000) { 
            showToast('⚠️ 页面无响应，跳脱清理...', '#ff4d4f', 3000);
            sessionStorage.setItem('matrix_last_healthy_time', Date.now().toString());
            sessionStorage.removeItem('matrix_auto_step'); 
            let hostUser = sessionStorage.getItem('matrix_target_username');
            if (hostUser && !window.location.href.includes('/followers')) { window.location.replace(`/${hostUser}/followers?_t=${Date.now()}`); } 
            else { let cleanUrl = window.location.href.split('?')[0]; window.location.replace(`${cleanUrl}?_t=${Date.now()}`); }
            return;
        }

        if (window.location.href.includes('/followers')) {
            let allCells = document.querySelectorAll('[data-testid="UserCell"]');
            if (allCells.length > 60) { for (let i = 0; i < 20; i++) { if (allCells[i] && allCells[i].parentNode) allCells[i].parentNode.removeChild(allCells[i]); } }
        }

        let warmupTime = parseInt(sessionStorage.getItem('matrix_warmup_timer') || '0');
        if (Date.now() < warmupTime) return;

        let memCount = parseInt(sessionStorage.getItem('matrix_mem_cleaner_count') || '0');
        if (memCount >= 35) {
            showToast('🧹 内存防爆击穿释放中...', '#f91880', 3000);
            sessionStorage.setItem('matrix_mem_cleaner_count', '0');
            sessionStorage.setItem('matrix_warmup_timer', (Date.now() + 5000).toString()); 
            let cleanUrl = window.location.href.split('?')[0];
            setTimeout(() => { window.location.replace(`${cleanUrl}?_t=${Date.now()}`); }, 1500);
            return;
        }

        const currentStep = sessionStorage.getItem('matrix_auto_step');

        if (!currentStep) {
            // V11.12.9+: 如果存在任务目标 handle，直接导航到该目标，不再随机扫 followers
            var taskTarget = (function() {
                try { return JSON.parse(localStorage.getItem('matrix_current_task') || 'null'); }
                catch(e) { return null; }
            })();
            var targetHandle = taskTarget && taskTarget.target && taskTarget.target.handle;
            if (targetHandle) {
                var normTarget = String(targetHandle).replace('@','').toLowerCase().trim();
                var currentPath = window.location.pathname.toLowerCase();
                if (!currentPath.includes(normTarget)) {
                    sessionStorage.setItem('matrix_target_username', normTarget);
                    window.location.href = '/' + normTarget;
                    return;
                }
                // 已经在目标 profile 页 -> 直接进入 step 1
                sessionStorage.setItem('current_target', normTarget);
                sessionStorage.setItem('matrix_auto_step', '1');
                return;
            }

            // 无任务目标，回退到旧版 followers 扫描
            if (!window.location.href.includes('/followers')) return;

            const userCells = document.querySelectorAll('[data-testid="UserCell"]');
            const scannedList = getSessionList();
            const rejectDB = getDB('reject_sent_users'); 
            let targetToClick = null;

            for (let cell of userCells) {
                let profileLink = cell.querySelector('a[role="link"]');
                if (profileLink) {
                    let rawHref = profileLink.getAttribute('href');
                    let userHandle = rawHref.split('?')[0].split('/').pop().toLowerCase();
                    if (rejectDB.has(userHandle)) { addSessionList(userHandle); continue; }
                    if (!targetToClick && !scannedList.includes(userHandle)) { targetToClick = { link: profileLink, handle: userHandle }; }
                }
            }

            if (targetToClick) {
                addSessionList(targetToClick.handle);
                sessionStorage.setItem('current_target', targetToClick.handle);
                sessionStorage.setItem('matrix_auto_step', '1');
                let randomReadTime = Math.floor(Math.random() * 2); 
                sessionStorage.setItem('matrix_profile_wait', randomReadTime.toString());
                targetToClick.link.click();
                sessionStorage.setItem('scroll_fail_count', '0');
                sessionStorage.setItem('matrix_bottom_hit_count', '0');
            } else {
                window.scrollBy({ top: 200, behavior: 'smooth' });
                let failCount = parseInt(sessionStorage.getItem('scroll_fail_count') || '0');
                sessionStorage.setItem('scroll_fail_count', failCount + 1);
                
                let isPhysicalBottom = (window.innerHeight + window.scrollY) >= document.documentElement.scrollHeight - 50;
                
                if (isPhysicalBottom) {
                    let hasLoader = document.querySelector('[role="progressbar"]');
                    let bottomHitCount = parseInt(sessionStorage.getItem('matrix_bottom_hit_count') || '0');
                    sessionStorage.setItem('matrix_bottom_hit_count', bottomHitCount + 1);
                    
                    if (!hasLoader && bottomHitCount >= 2) {
                        showToast('✅ 彻底触底！确认无新数据，重置...', '#1d9bf0', 3000);
                        sessionStorage.setItem('matrix_session_scanned', '[]');
                        sessionStorage.setItem('scroll_fail_count', '0');
                        sessionStorage.setItem('matrix_bottom_hit_count', '0');
                        sessionStorage.setItem('matrix_warmup_timer', (Date.now() + 3000).toString());
                        let cleanUrl = window.location.href.split('?')[0];
                        setTimeout(() => { window.scrollTo(0,0); window.location.replace(`${cleanUrl}?_t=${Date.now()}`); }, 1500);
                    } else if (hasLoader) {
                        sessionStorage.setItem('matrix_bottom_hit_count', '0');
                        showToast('⏳ 等待拉取新粉丝中...', '#faad14', 1500);
                    } else {
                        showToast('⏬ 触底辅助确认中...', '#faad14', 1500);
                    }
                } else {
                    sessionStorage.setItem('matrix_bottom_hit_count', '0');
                    if (failCount > 100) {
                        sessionStorage.setItem('matrix_session_scanned', '[]');
                        sessionStorage.setItem('scroll_fail_count', '0');
                        let cleanUrl = window.location.href.split('?')[0];
                        window.location.replace(`${cleanUrl}?_t=${Date.now()}`);
                    }
                }
            }
        }

        if (currentStep === '1') {
            let pageText = document.body.innerText;
            if (pageText.includes('此账号不存在') || pageText.includes('This account doesn\'t exist') || pageText.includes('账号已冻结') || pageText.includes('Account suspended')) {
                showToast('💀 账号已阵亡，跳过！', '#000', 3000);
                let deadHandle = sessionStorage.getItem('current_target');
                if (deadHandle) { saveToDB('reject_sent_users', deadHandle); sendLogToNAS(deadHandle, 'CORPSE', '封号阵亡'); try { guardFailAction('corpse', { error_code: 'suspended', error_message: 'account_suspended', target_handle: deadHandle }); } catch(e) {} }
                sessionStorage.setItem('matrix_auto_step', '4');
                return;
            }

            let dmButton = document.querySelector('[data-testid="sendDMFromProfile"]');
            if (dmButton) {
                let waitCount = parseInt(sessionStorage.getItem('matrix_profile_wait') || '0');
                if (waitCount > 0) {
                    let randomDir = Math.random() > 0.4 ? 1 : -0.5;
                    window.scrollBy({ top: randomDir * (200 + Math.random()*200), behavior: 'smooth' });
                    sessionStorage.setItem('matrix_profile_wait', (waitCount - 1).toString());
                    return; 
                }
                sessionStorage.setItem('matrix_auto_step', '2');
                sessionStorage.setItem('matrix_chat_wait_time', '0');
                setTimeout(() => { dmButton.click(); }, 600);
            } else {
                let failDMCount = parseInt(sessionStorage.getItem('matrix_wait_count') || '0');
                if (failDMCount > 4) {
                    showToast('⚠️ 未开启私信，跳过！', '#f91880');
                    let targetHandle = sessionStorage.getItem('current_target');
                    sendLogToNAS(targetHandle, 'REJECT', '未开启私信');
                    try { guardFailAction('reject', { error_code: 'dm_closed', error_message: 'dm_not_open', target_handle: targetHandle }); } catch(e) {}
                    sessionStorage.setItem('matrix_auto_step', '4');
                } else { sessionStorage.setItem('matrix_wait_count', failDMCount + 1); }
            }
        }

        if (currentStep === '2') {
            const wakeUpTarget = findBottomAwakeningTarget();
            if (!wakeUpTarget) return;

            const targetHandle = sessionStorage.getItem('current_target');

            // ========== 【尸体时间过滤：超过昨天未互动的直接跳过】 ==========
            let latestMsgAge = getLatestMessageAgeDays();
            if (latestMsgAge >= 2) {
                showToast(`💀 超过${latestMsgAge}天未互动，标记尸体`, '#536471');
                sendLogToNAS(targetHandle, 'CORPSE', `${latestMsgAge}天未互动-尸体`);
                try { guardFailAction('corpse', { error_code: 'corpse', error_message: 'stale_thread', target_handle: targetHandle }); } catch(e) {}
                saveToDB('reject_sent_users', targetHandle);
                sessionStorage.setItem('matrix_mem_cleaner_count', (parseInt(sessionStorage.getItem('matrix_mem_cleaner_count') || '0') + 1).toString());
                sessionStorage.setItem('matrix_auto_step', '4');
                return;
            }

            let waitCount = parseInt(sessionStorage.getItem('matrix_chat_wait_time') || '0');
            let decision = getChatDecision(targetHandle);

            if (decision.action === 'STILL_LOADING') {
                if (waitCount >= 8) {
                    showToast('❌ 加载超时，跳脱！', '#ff4d4f', 2000);
                    sessionStorage.setItem('matrix_mem_cleaner_count', (parseInt(sessionStorage.getItem('matrix_mem_cleaner_count') || '0') + 1).toString());
                    sessionStorage.setItem('matrix_auto_step', '4');
                    return;
                }
                showToast(`⏳ 聊天加载中... (${waitCount}/8)`, '#faad14', 1500);
                sessionStorage.setItem('matrix_chat_wait_time', waitCount + 1); return;
            }

            sessionStorage.setItem('matrix_auto_step', '2_waiting');
            let msgToSend = null;

            if (decision.action === 'SKIP_WAITING') { showToast('💤 等待回复中...', '#536471'); }
            else if (decision.action === 'SEND_ICEBREAKER') { msgToSend = ICEBREAKER_MESSAGE; showToast('❄️ 发破冰！', '#1d9bf0'); sendLogToNAS(targetHandle, 'ICEBREAKER', '破冰'); }
            else if (decision.action === 'SEND_REJECT') { msgToSend = REJECT_MESSAGE; showToast('⛔ 低龄婉拒', '#f91880'); sendLogToNAS(targetHandle, 'REJECT', '低龄'); try { guardFailAction('reject', { error_code: 'reject', error_message: 'age_reject', target_handle: targetHandle }); } catch(e) {} }
            else if (decision.action === 'SEND_FOREIGNER_REJECT') { msgToSend = FOREIGNER_REJECT_MESSAGE; showToast('🌍 老外婉拒', '#f91880'); sendLogToNAS(targetHandle, 'REJECT', '外语'); try { guardFailAction('reject', { error_code: 'foreign_reject', error_message: 'language_reject', target_handle: targetHandle }); } catch(e) {} }
            else if (decision.action === 'SKIP_REJECTED') { showToast('⛔ 已黑名单，秒退', '#f91880'); }
            else if (decision.action === 'SKIP_MAXED') { showToast('🛡️ 死尸号，跳过', '#536471'); sendLogToNAS(targetHandle, 'IGNORED', '死尸跳过'); try { guardFailAction('ignored', { error_code: 'skip_maxed', error_message: 'dead_account', target_handle: targetHandle }); } catch(e) {} }
            else if (decision.action === 'SEND_AD') {
                let randomLink = getLiveLink();
                if (!randomLink) {
                    console.error('[活水] 🚨 链接不可用，阻止发送广告！');
                    showToast('🚨 链接不可用，广告已阻止', '#f91880');
                    return;  // 阻止发送
                }
                msgToSend = AD_MESSAGE_TEMPLATE.replace('{LINK}', randomLink);
                showToast('🎣 发广告', '#1d9bf0');
                sendLogToNAS(targetHandle, 'AD', `发送了引流链接`);
            }
            else if (decision.action === 'SEND_KICK') { msgToSend = KICK_MESSAGE; showToast('🛡️ 发送盾牌', '#faad14'); sendLogToNAS(targetHandle, 'AD', '发防漏盾牌'); }

            if (msgToSend) {
                threadSafeSend(wakeUpTarget, msgToSend);
                sessionStorage.setItem('matrix_sent_' + targetHandle, 'true');
                try {
                    if (decision.action === 'SEND_ICEBREAKER') {
                        guardCompleteAction('icebreaker', { target_handle: targetHandle, detail: '破冰' });
                    } else if (decision.action === 'SEND_AD') {
                        guardCompleteAction('ad', { target_handle: targetHandle, detail: '广告' });
                    } else if (decision.action === 'SEND_KICK') {
                        guardCompleteAction('ad', { target_handle: targetHandle, detail: '盾牌' });
                    }
                } catch(e) {}
                setTimeout(() => { 
                    sessionStorage.setItem('matrix_mem_cleaner_count', (parseInt(sessionStorage.getItem('matrix_mem_cleaner_count') || '0') + 1).toString());
                    sessionStorage.setItem('matrix_auto_step', '4'); 
                }, 2500 + Math.floor(Math.random() * 1500));
            } else {
                sessionStorage.setItem('matrix_mem_cleaner_count', (parseInt(sessionStorage.getItem('matrix_mem_cleaner_count') || '0') + 1).toString());
                sessionStorage.setItem('matrix_auto_step', '4');
            }
        }

        if (currentStep === '4') {
            sessionStorage.removeItem('matrix_auto_step');
            showToast('🔙 返回...', '#1d9bf0', 1000);
            // 任务目标模式：执行完任务目标后停止引擎，等待下个任务
            var taskAfterAction = (function() {
                try { return JSON.parse(localStorage.getItem('matrix_current_task') || 'null'); }
                catch(e) { return null; }
            })();
            if (taskAfterAction && taskAfterAction.target && taskAfterAction.target.handle) {
                localStorage.removeItem('matrix_current_task');
                localStorage.removeItem('matrix_current_task_id');
                localStorage.removeItem('matrix_current_action_plan');
                sessionStorage.setItem('matrix_auto_run', 'false');
                showToast('✅ 任务目标处理完成，等待下个任务', '#1d9bf0', 3000);
                return;
            }
            let hostUser = sessionStorage.getItem('matrix_target_username');
            if (hostUser) { window.location.replace(`/${hostUser}/followers?_t=${Date.now()}`); } 
            else { let cleanUrl = window.location.href.split('?')[0]; window.location.replace(`${cleanUrl}?_t=${Date.now()}`); }
            sessionStorage.setItem('matrix_warmup_timer', (Date.now() + 3000).toString());
        }

    }, 5000 + Math.floor(Math.random() * 2000));

    // ==============================================================================
    // 探针模块 (V11.4 修复：心跳始终上报，不受 matrix_auto_run 限制)
    // ==============================================================================
    setInterval(() => {
        // 移除 if (sessionStorage.getItem('matrix_auto_run') !== 'true') return; 限制
        
        let workerId = getWorkerId();
        
        // 根据引擎实际状态设置心跳状态
        let isEngineRunning = sessionStorage.getItem('matrix_auto_run') === 'true';
        let currentStatus = isEngineRunning ? "正在列表中寻敌..." : "私信引擎待机";
        let target = sessionStorage.getItem('current_target') || "无";
        let detailStr = `当前操作目标: @${target}`;

        if (sessionStorage.getItem('matrix_cooling_down') === 'true') {
            currentStatus = "风控强制休眠中";
        }
        
        let lastHealthy = parseInt(sessionStorage.getItem('matrix_last_healthy_time') || Date.now());
        if (Date.now() - lastHealthy > 25000) {
            currentStatus = "⚠️ 页面白屏卡死 (看门狗待命中)";
            detailStr = "DOM节点无响应";
        } else if (sessionStorage.getItem('matrix_auto_step') === '2_waiting') {
            currentStatus = "私信分析与发送中...";
        }

        // 读取本地累计统计，随心跳同步到 NAS（解决大屏显示为0的问题）
        let rawStats = GM_getValue('matrix_local_stats', '');
        let localStats = rawStats ? JSON.parse(rawStats) : {ice:0, ad:0, corpse:0, reject:0};
        if (localStats.ignored !== undefined && localStats.corpse === undefined) {
            localStats.corpse = localStats.ignored; localStats.reject = 0;
        }

        // 通过 background.js 上报（避免 HTTPS 页面的 Mixed Content 问题）
        try {
            chrome.runtime.sendMessage({
                action: "send_report",
                payload: {
                    worker_id: workerId,
                    engine: "chat",
                    status: currentStatus,
                    detail: detailStr,
                    stats: {
                        ice: localStats.ice || 0,
                        ad: localStats.ad || 0,
                        corpse: localStats.corpse || 0,
                        reject: localStats.reject || 0
                    }
                }
            }, (response) => {
                if (chrome.runtime.lastError) {
                    console.log('[心跳] Service Worker 未就绪');
                }
            });
        } catch(e) {}
    }, 5000); // 5秒心跳

})();
