// X-Matrix 诊断工具 JavaScript

// ================= 【配置】 =================
const DEFAULT_NAS_URL = 'http://192.168.0.100:5678';
const DEFAULT_WORKER_ID = 'test-worker';

// 日志存储
let logEntries = [];

// ================= 【工具函数】 =================

function addLog(level, message) {
    const time = new Date().toLocaleTimeString();
    logEntries.push({ time, level, message });
    
    const logViewer = document.getElementById('log-viewer');
    const logLine = document.createElement('div');
    logLine.className = 'log-line';
    logLine.innerHTML = `<span class="log-time">${time}</span> <span class="log-level-${level}">${message}</span>`;
    logViewer.appendChild(logLine);
    logViewer.scrollTop = logViewer.scrollHeight;
}

function showResult(elementId, type, message) {
    const element = document.getElementById(elementId);
    element.className = `result ${type}`;
    element.textContent = message;
    element.style.display = 'block';
}

function hideResult(elementId) {
    const element = document.getElementById(elementId);
    element.style.display = 'none';
}

function getTimestamp() {
    return new Date().toISOString();
}

// ================= 【NAS 连接测试】 =================

async function testNAS() {
    const nasUrl = document.getElementById('nas-url').value;
    const btn = document.getElementById('btn-test-nas');
    
    btn.disabled = true;
    btn.textContent = '测试中...';
    hideResult('nas-result');
    addLog('info', `测试 NAS 连接: ${nasUrl}`);
    
    try {
        const startTime = Date.now();
        const response = await fetch(`${nasUrl}/health`, {
            method: 'GET',
            signal: AbortSignal.timeout(5000)
        });
        const elapsed = Date.now() - startTime;
        
        if (response.ok) {
            const data = await response.json();
            showResult('nas-result', 'success', `✅ NAS 可达 (HTTP ${response.status}, ${elapsed}ms)`);
            addLog('success', `NAS 连接成功: ${elapsed}ms`);
        } else {
            showResult('nas-result', 'error', `❌ NAS 返回错误: HTTP ${response.status}`);
            addLog('error', `NAS 连接失败: HTTP ${response.status}`);
        }
    } catch (error) {
        showResult('nas-result', 'error', `❌ NAS 不可达: ${error.message}`);
        addLog('error', `NAS 连接异常: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '测试';
    }
}

// ================= 【SSE 连接测试】 =================

let sseConnection = null;

function testSSE() {
    const nasUrl = document.getElementById('nas-url').value;
    const workerId = document.getElementById('worker-id').value;
    
    hideResult('sse-result');
    document.getElementById('sse-messages').innerHTML = '';
    
    // 关闭旧连接
    if (sseConnection) {
        sseConnection.close();
        sseConnection = null;
    }
    
    const url = `${nasUrl}/events/${encodeURIComponent(workerId)}`;
    addLog('info', `测试 SSE 连接: ${url}`);
    
    let messageCount = 0;
    const startTime = Date.now();
    
    sseConnection = new EventSource(url);
    
    sseConnection.onopen = () => {
        showResult('sse-result', 'success', '✅ SSE 连接成功');
        addLog('success', 'SSE 连接已建立');
        document.getElementById('btn-stop-sse').disabled = false;
    };
    
    sseConnection.onmessage = (e) => {
        messageCount++;
        const elapsed = Date.now() - startTime;
        
        const messageDiv = document.getElementById('sse-messages');
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.innerHTML = `<span class="time">${new Date().toLocaleTimeString()}</span> <span class="data">${e.data}</span>`;
        messageDiv.appendChild(entry);
        messageDiv.scrollTop = messageDiv.scrollHeight;
        
        addLog('info', `收到消息 #${messageCount}: ${e.data}`);
        
        // 更新状态
        showResult('sse-result', 'success', `✅ SSE 连接正常 | 消息数: ${messageCount} | 运行时间: ${Math.round(elapsed / 1000)}s`);
    };
    
    sseConnection.onerror = () => {
        showResult('sse-result', 'error', '❌ SSE 连接错误');
        addLog('error', 'SSE 连接错误');
        sseConnection.close();
        sseConnection = null;
        document.getElementById('btn-stop-sse').disabled = true;
    };
}

function stopSSE() {
    if (sseConnection) {
        sseConnection.close();
        sseConnection = null;
        addLog('info', 'SSE 连接已手动关闭');
        document.getElementById('btn-stop-sse').disabled = true;
        showResult('sse-result', 'warning', '⚠️ SSE 连接已关闭');
    }
}

// ================= 【心跳状态】 =================

async function refreshHeartbeat() {
    addLog('info', '刷新心跳状态...');
    
    try {
        const result = await chrome.storage.local.get([
            'matrix_last_heartbeat',
            'matrix_last_heartbeat_time',
            'matrix_worker_id'
        ]);
        
        const lastHeartbeat = result.matrix_last_heartbeat;
        const lastTime = result.matrix_last_heartbeat_time;
        const workerId = result.matrix_worker_id;
        
        // 更新显示
        document.getElementById('last-heartbeat').textContent = lastTime 
            ? new Date(lastTime).toLocaleString() 
            : '-';
        document.getElementById('worker-id-display').textContent = workerId || '-';
        document.getElementById('engine-status').textContent = lastHeartbeat?.status || '-';
        
        addLog('success', '心跳状态已刷新');
    } catch (error) {
        addLog('error', `刷新心跳状态失败: ${error.message}`);
    }
}

// ================= 【代理测试】 =================

async function testDirect() {
    const nasUrl = document.getElementById('nas-url').value;
    hideResult('proxy-result');
    addLog('info', '测试直连...');
    
    try {
        const startTime = Date.now();
        const response = await fetch(`${nasUrl}/health`, {
            method: 'GET',
            signal: AbortSignal.timeout(5000)
        });
        const elapsed = Date.now() - startTime;
        
        if (response.ok) {
            showResult('proxy-result', 'success', `✅ 直连可达 (${elapsed}ms)`);
            addLog('success', `直连测试成功: ${elapsed}ms`);
        } else {
            showResult('proxy-result', 'error', `❌ 直连失败: HTTP ${response.status}`);
            addLog('error', `直连测试失败: HTTP ${response.status}`);
        }
    } catch (error) {
        showResult('proxy-result', 'error', `❌ 直连不可达: ${error.message}`);
        addLog('error', `直连测试异常: ${error.message}`);
    }
}

async function testProxy() {
    const proxyUrl = document.getElementById('proxy-url').value;
    const nasUrl = document.getElementById('nas-url').value;
    hideResult('proxy-result');
    addLog('info', `测试代理: ${proxyUrl}`);
    
    // 注意：浏览器扩展无法直接测试代理，这里只是提示
    showResult('proxy-result', 'warning', '⚠️ 浏览器扩展无法直接测试代理连接，请在系统代理设置中检查');
    addLog('warn', '代理测试需要在系统设置中验证');
}

// ================= 【日志查看器】 =================

async function refreshLogs() {
    addLog('info', '刷新日志...');
    
    // 从 chrome.storage.local 读取日志
    try {
        const result = await chrome.storage.local.get(['matrix_logs']);
        const logs = result.matrix_logs || [];
        
        const logViewer = document.getElementById('log-viewer');
        logViewer.innerHTML = '';
        
        logs.forEach(log => {
            const logLine = document.createElement('div');
            logLine.className = 'log-line';
            logLine.innerHTML = `<span class="log-time">${log.time}</span> <span class="log-level-${log.level}">${log.message}</span>`;
            logViewer.appendChild(logLine);
        });
        
        addLog('success', `已加载 ${logs.length} 条日志`);
    } catch (error) {
        addLog('error', `读取日志失败: ${error.message}`);
    }
}

function clearLogs() {
    logEntries = [];
    document.getElementById('log-viewer').innerHTML = '';
    addLog('info', '日志已清空');
}

function exportLogs() {
    const logText = logEntries.map(entry => `[${entry.time}] [${entry.level.toUpperCase()}] ${entry.message}`).join('\n');
    
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `xmatrix-diagnostic-${new Date().toISOString().slice(0, 10)}.log`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    addLog('success', '日志已导出');
}

// ================= 【诊断报告】 =================

async function generateReport() {
    addLog('info', '生成诊断报告...');
    
    const nasUrl = document.getElementById('nas-url').value;
    const proxyUrl = document.getElementById('proxy-url').value;
    
    let report = `X-Matrix 诊断报告\n`;
    report += `生成时间: ${getTimestamp()}\n`;
    report += `${'='.repeat(50)}\n\n`;
    
    // NAS 连接测试
    report += `【NAS 连接测试】\n`;
    try {
        const startTime = Date.now();
        const response = await fetch(`${nasUrl}/health`, {
            method: 'GET',
            signal: AbortSignal.timeout(5000)
        });
        const elapsed = Date.now() - startTime;
        report += `状态: ${response.ok ? '✅ 可达' : '❌ 不可达'}\n`;
        report += `响应时间: ${elapsed}ms\n`;
        report += `HTTP 状态: ${response.status}\n`;
    } catch (error) {
        report += `状态: ❌ 不可达\n`;
        report += `错误: ${error.message}\n`;
    }
    report += `\n`;
    
    // 心跳状态
    report += `【心跳状态】\n`;
    try {
        const result = await chrome.storage.local.get([
            'matrix_last_heartbeat',
            'matrix_last_heartbeat_time',
            'matrix_worker_id'
        ]);
        
        report += `Worker ID: ${result.matrix_worker_id || '未设置'}\n`;
        report += `最后心跳: ${result.matrix_last_heartbeat_time ? new Date(result.matrix_last_heartbeat_time).toLocaleString() : '无'}\n`;
        report += `引擎状态: ${result.matrix_last_heartbeat?.status || '未知'}\n`;
    } catch (error) {
        report += `读取失败: ${error.message}\n`;
    }
    report += `\n`;
    
    // 配置信息
    report += `【配置信息】\n`;
    report += `NAS 地址: ${nasUrl}\n`;
    report += `代理地址: ${proxyUrl}\n`;
    report += `扩展版本: 11.7.0\n`;
    report += `\n`;
    
    // 日志
    report += `【最近日志】\n`;
    logEntries.slice(-20).forEach(entry => {
        report += `[${entry.time}] [${entry.level.toUpperCase()}] ${entry.message}\n`;
    });
    
    document.getElementById('diagnostic-report').value = report;
    document.getElementById('btn-copy-report').disabled = false;
    
    addLog('success', '诊断报告已生成');
}

function copyReport() {
    const report = document.getElementById('diagnostic-report').value;
    navigator.clipboard.writeText(report).then(() => {
        addLog('success', '诊断报告已复制到剪贴板');
        alert('诊断报告已复制到剪贴板');
    }).catch(error => {
        addLog('error', `复制失败: ${error.message}`);
    });
}

// ================= 【一键测试全部】 =================

async function testAll() {
    addLog('info', '开始一键测试...');
    
    await testNAS();
    await refreshHeartbeat();
    testSSE();
    
    addLog('info', '一键测试完成');
}

// ================= 【事件绑定】 =================

document.addEventListener('DOMContentLoaded', () => {
    // NAS 测试
    document.getElementById('btn-test-nas').addEventListener('click', testNAS);
    
    // SSE 测试
    document.getElementById('btn-test-sse').addEventListener('click', testSSE);
    document.getElementById('btn-stop-sse').addEventListener('click', stopSSE);
    
    // 心跳刷新
    document.getElementById('btn-refresh-heartbeat').addEventListener('click', refreshHeartbeat);
    
    // 代理测试
    document.getElementById('btn-test-direct').addEventListener('click', testDirect);
    document.getElementById('btn-test-proxy').addEventListener('click', testProxy);
    
    // 日志
    document.getElementById('btn-refresh-logs').addEventListener('click', refreshLogs);
    document.getElementById('btn-clear-logs').addEventListener('click', clearLogs);
    document.getElementById('btn-export-logs').addEventListener('click', exportLogs);
    
    // 诊断报告
    document.getElementById('btn-generate-report').addEventListener('click', generateReport);
    document.getElementById('btn-copy-report').addEventListener('click', copyReport);
    
    // 一键测试
    document.getElementById('btn-test-all').addEventListener('click', testAll);
    
    // 初始化
    addLog('info', '诊断工具已加载');
    refreshHeartbeat();
});
