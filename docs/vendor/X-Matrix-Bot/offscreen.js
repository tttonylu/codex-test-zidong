// ==============================================================================
// X-Matrix-Bot Offscreen 后台页面 (V11.5.7 SSE 版)
// 作用：绕过 MV3 Service Worker 休眠限制，持久化运行网络请求
// Chrome 109+ 支持 chrome.offscreen API
// 功能：SSE 长连接接收指令 + HTTP 心跳上报 + HTTP 战报上报
// ==============================================================================

const LOG_SERVER_URL = "http://192.168.0.100:5678";
const API_TOKEN = "xm2026_a1b2c3d4e5";

// SSE 配置
const SSE_RETRY_INTERVAL = 30000;  // 30秒后重试 SSE
const POLL_INTERVAL = 15000;       // 轮询间隔 15秒

let transportMode = 'sse';  // 'sse' | 'polling'
let sseConnection = null;
let pollingTimer = null;
let currentWorkerId = null;

console.log('[offscreen] 后台页面已启动 (SSE 版)，时间:', new Date().toISOString());

// ================= 【SSE 连接管理】 =================

function connectSSE(workerId) {
    if (!workerId) {
        console.warn('[SSE] workerId 未设置，跳过连接');
        return;
    }
    
    const url = `${LOG_SERVER_URL}/events/${encodeURIComponent(workerId)}`;
    console.log('[SSE] 尝试连接:', url);
    
    // 关闭旧连接
    if (sseConnection) {
        sseConnection.close();
        sseConnection = null;
    }
    
    sseConnection = new EventSource(url);
    
    sseConnection.onopen = () => {
        transportMode = 'sse';
        console.log('[SSE] ✅ 连接成功，使用 SSE 模式');
        stopPolling();  // 停止轮询
    };
    
    sseConnection.onmessage = (e) => {
        // 忽略 keepalive 注释行
        if (!e.data || e.data === 'keepalive') return;
        
        try {
            const cmd = JSON.parse(e.data);
            console.log('[SSE] 收到指令:', cmd);
            
            // 转发指令到 background.js 执行
            chrome.runtime.sendMessage({
                action: 'execute_command',
                payload: cmd
            }, (response) => {
                if (chrome.runtime.lastError) {
                    console.error('[SSE] 转发指令失败:', chrome.runtime.lastError.message);
                } else {
                    console.log('[SSE] 指令已转发:', response);
                }
            });
        } catch (err) {
            console.error('[SSE] 解析指令失败:', err, '原始数据:', e.data);
        }
    };
    
    sseConnection.onerror = (e) => {
        console.warn('[SSE] ❌ 连接错误，降级为 HTTP 轮询');
        transportMode = 'polling';
        sseConnection.close();
        sseConnection = null;
        startPolling(workerId);
    };
}

function startPolling(workerId) {
    if (pollingTimer) return;  // 已在轮询中
    
    console.log('[轮询] 启动 HTTP 轮询模式，间隔:', POLL_INTERVAL / 1000, '秒');
    
    pollingTimer = setInterval(async () => {
        try {
            const resp = await fetch(`${LOG_SERVER_URL}/api/actions`, {
                headers: { 'X-API-Token': API_TOKEN }
            });
            
            if (!resp.ok) {
                console.error('[轮询] 请求失败，HTTP 状态:', resp.status);
                return;
            }
            
            const data = await resp.json();
            if (data.ok && data.actions && data.actions.length > 0) {
                console.log('[轮询] 收到', data.actions.length, '个指令');
                data.actions.forEach(cmd => {
                    chrome.runtime.sendMessage({
                        action: 'execute_command',
                        payload: cmd
                    }, (response) => {
                        if (chrome.runtime.lastError) {
                            console.error('[轮询] 转发指令失败:', chrome.runtime.lastError.message);
                        }
                    });
                });
            }
        } catch (e) {
            console.error('[轮询] 请求异常:', e);
        }
    }, POLL_INTERVAL);
    
    // 30秒后尝试恢复 SSE
    setTimeout(() => {
        if (transportMode === 'polling' && currentWorkerId) {
            console.log('[轮询] 尝试恢复 SSE 连接...');
            stopPolling();
            connectSSE(currentWorkerId);
        }
    }, SSE_RETRY_INTERVAL);
}

function stopPolling() {
    if (pollingTimer) {
        clearInterval(pollingTimer);
        pollingTimer = null;
        console.log('[轮询] 已停止');
    }
}

// ================= 【消息监听】 =================

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    // 战报转发
    if (request.action === "offscreen_log_action") {
        const payload = request.payload;
        console.log('[offscreen] 收到战报:', payload.action_type, '| target=', payload.target, '| bot_id=', payload.bot_id);
        
        fetch(LOG_SERVER_URL + '/log_action', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json', 
                'X-API-Token': API_TOKEN 
            },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) {
                console.error('[offscreen] 战报上报失败，HTTP 状态:', response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log('[offscreen] 战报上报成功:', data);
        })
        .catch(error => {
            console.error('[offscreen] 战报上报异常:', error);
        });
    }
    
    // 心跳转发
    if (request.action === "offscreen_send_report") {
        const payload = request.payload;
        console.log('[offscreen] 收到心跳:', payload.worker_id, '| engine=', payload.engine, '| status=', payload.status);
        
        fetch(LOG_SERVER_URL + '/report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Token': API_TOKEN
            },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) {
                console.error('[offscreen] 心跳上报失败，HTTP 状态:', response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log('[offscreen] 心跳上报成功:', data);
            sendResponse({status: "success", data: data});
        })
        .catch(error => {
            console.error('[offscreen] 心跳上报异常:', error);
            sendResponse({status: "error", message: error.message});
        });
        
        return true; // 保持 sendResponse 通道开放
    }
    
    // SSE 连接请求（从 background.js 转发）
    if (request.action === "connect_sse") {
        currentWorkerId = request.worker_id;
        console.log('[offscreen] 收到 SSE 连接请求，workerId:', currentWorkerId);
        connectSSE(currentWorkerId);
        sendResponse({status: "connecting"});
        return true;
    }
});

// ================= 【初始化】 =================

// 监听 background.js 发送的初始化消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "init_offscreen") {
        currentWorkerId = request.worker_id;
        console.log('[offscreen] 收到初始化消息，workerId:', currentWorkerId);
        
        // 启动 SSE 连接
        if (currentWorkerId) {
            connectSSE(currentWorkerId);
        }
        
        sendResponse({status: "initialized"});
        return true;
    }
});

console.log('[offscreen] 监听已就绪，等待消息...');
