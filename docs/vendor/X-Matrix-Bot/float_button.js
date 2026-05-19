// X-Matrix 浮动状态按钮
// 在 X/Twitter 页面右下角显示扩展状态

(function() {
    'use strict';

    // 防止重复注入
    if (document.getElementById('xmatrix-float-btn')) return;

    const NAS_URL = 'http://192.168.0.100:5678';

    // ================= 【创建浮动按钮】 =================

    function createFloatButton() {
        const btn = document.createElement('div');
        btn.id = 'xmatrix-float-btn';
        btn.innerHTML = '🔧';
        btn.title = 'X-Matrix 状态检查';
        btn.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #1d9bf0;
            color: white;
            font-size: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            z-index: 999999;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            transition: all 0.2s;
            user-select: none;
        `;

        btn.addEventListener('mouseenter', () => {
            btn.style.transform = 'scale(1.1)';
            btn.style.boxShadow = '0 4px 15px rgba(0,0,0,0.4)';
        });

        btn.addEventListener('mouseleave', () => {
            btn.style.transform = 'scale(1)';
            btn.style.boxShadow = '0 2px 10px rgba(0,0,0,0.3)';
        });

        btn.addEventListener('click', showStatusPopup);
        document.body.appendChild(btn);

        return btn;
    }

    // ================= 【状态检查】 =================

    async function checkStatus() {
        const status = {
            extension: { icon: '⏳', text: '检查中...', color: '#8899a6' },
            nas: { icon: '⏳', text: '检查中...', color: '#8899a6' },
            sse: { icon: '⏳', text: '检查中...', color: '#8899a6' },
            heartbeat: { icon: '⏳', text: '检查中...', color: '#8899a6' },
            workerId: '-'
        };

        // 检查扩展状态
        try {
            const pingResponse = await chrome.runtime.sendMessage({ action: 'ping' });
            if (pingResponse && pingResponse.status === 'pong') {
                status.extension = { icon: '✅', text: '运行中', color: '#00ba7c' };
            } else {
                status.extension = { icon: '⚠️', text: '响应异常', color: '#ffd700' };
            }
        } catch (e) {
            status.extension = { icon: '❌', text: '未响应', color: '#f91880' };
        }

        // 检查 NAS 连接
        try {
            const start = Date.now();
            const response = await fetch(`${NAS_URL}/health`, {
                method: 'GET',
                signal: AbortSignal.timeout(3000)
            });
            const elapsed = Date.now() - start;
            if (response.ok) {
                status.nas = { icon: '✅', text: `可达 (${elapsed}ms)`, color: '#00ba7c' };
            } else {
                status.nas = { icon: '❌', text: `HTTP ${response.status}`, color: '#f91880' };
            }
        } catch (e) {
            status.nas = { icon: '❌', text: '不可达', color: '#f91880' };
        }

        // 检查 SSE 状态和心跳
        try {
            const storage = await chrome.storage.local.get([
                'matrix_worker_id',
                'matrix_sse_mode',
                'matrix_last_heartbeat_time'
            ]);

            status.workerId = storage.matrix_worker_id || '未设置';

            const mode = storage.matrix_sse_mode || 'unknown';
            const lastTime = storage.matrix_last_heartbeat_time || 0;
            const heartbeatAge = Date.now() - lastTime;

            // 如果有最近的心跳（10秒内），说明连接正常
            if (heartbeatAge < 10000) {
                if (mode === 'sse') {
                    status.sse = { icon: '✅', text: 'SSE 模式', color: '#00ba7c' };
                } else if (mode === 'polling') {
                    status.sse = { icon: '⚠️', text: 'HTTP 轮询', color: '#ffd700' };
                } else {
                    status.sse = { icon: '✅', text: '已连接', color: '#00ba7c' };
                }
            } else if (mode === 'sse') {
                status.sse = { icon: '✅', text: 'SSE 模式', color: '#00ba7c' };
            } else if (mode === 'polling') {
                status.sse = { icon: '⚠️', text: 'HTTP 轮询', color: '#ffd700' };
            } else if (mode === 'connecting') {
                status.sse = { icon: 'ℹ️', text: '连接中...', color: '#1d9bf0' };
            } else {
                status.sse = { icon: '⚠️', text: '未连接', color: '#ffd700' };
            }

            const lastTime = storage.matrix_last_heartbeat_time;
            if (lastTime) {
                const elapsed = Date.now() - lastTime;
                const seconds = Math.round(elapsed / 1000);
                if (seconds < 10) {
                    status.heartbeat = { icon: '✅', text: `${seconds}秒前`, color: '#00ba7c' };
                } else if (seconds < 60) {
                    status.heartbeat = { icon: '⚠️', text: `${seconds}秒前`, color: '#ffd700' };
                } else {
                    status.heartbeat = { icon: '❌', text: `${seconds}秒前`, color: '#f91880' };
                }
            } else {
                status.heartbeat = { icon: '⚠️', text: '无记录', color: '#ffd700' };
            }
        } catch (e) {
            status.sse = { icon: '❌', text: '检查失败', color: '#f91880' };
            status.heartbeat = { icon: '❌', text: '检查失败', color: '#f91880' };
        }

        return status;
    }

    // ================= 【显示状态弹窗】 =================

    async function showStatusPopup() {
        // 移除旧弹窗
        const oldPopup = document.getElementById('xmatrix-status-popup');
        if (oldPopup) {
            oldPopup.remove();
            return;
        }

        // 创建弹窗
        const popup = document.createElement('div');
        popup.id = 'xmatrix-status-popup';
        popup.style.cssText = `
            position: fixed;
            bottom: 70px;
            right: 20px;
            width: 280px;
            background: #1c2732;
            border: 1px solid #38444d;
            border-radius: 12px;
            padding: 16px;
            z-index: 999998;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 13px;
            color: #e7e9ea;
        `;

        popup.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #38444d;">
                <span style="font-weight: 600;">🔧 X-Matrix 状态</span>
                <span style="font-size: 11px; color: #8899a6;">V11.7.0</span>
            </div>
            <div id="xmatrix-status-content">
                <div style="text-align: center; color: #8899a6;">检查中...</div>
            </div>
            <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #38444d; text-align: center;">
                <button id="xmatrix-btn-diagnostic" style="background: #1d9bf0; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px;">打开诊断工具</button>
            </div>
        `;

        document.body.appendChild(popup);

        // 检查状态
        const status = await checkStatus();

        // 更新内容
        const content = document.getElementById('xmatrix-status-content');
        content.innerHTML = `
            <div style="display: flex; align-items: center; padding: 6px 0;">
                <span style="width: 20px; text-align: center;">${status.extension.icon}</span>
                <span style="flex: 1; color: #8899a6;">扩展状态</span>
                <span style="color: ${status.extension.color};">${status.extension.text}</span>
            </div>
            <div style="display: flex; align-items: center; padding: 6px 0;">
                <span style="width: 20px; text-align: center;">${status.nas.icon}</span>
                <span style="flex: 1; color: #8899a6;">NAS 连接</span>
                <span style="color: ${status.nas.color};">${status.nas.text}</span>
            </div>
            <div style="display: flex; align-items: center; padding: 6px 0;">
                <span style="width: 20px; text-align: center;">${status.sse.icon}</span>
                <span style="flex: 1; color: #8899a6;">SSE 模式</span>
                <span style="color: ${status.sse.color};">${status.sse.text}</span>
            </div>
            <div style="display: flex; align-items: center; padding: 6px 0;">
                <span style="width: 20px; text-align: center;">${status.heartbeat.icon}</span>
                <span style="flex: 1; color: #8899a6;">最后心跳</span>
                <span style="color: ${status.heartbeat.color};">${status.heartbeat.text}</span>
            </div>
            <div style="display: flex; align-items: center; padding: 6px 0;">
                <span style="width: 20px; text-align: center;">👤</span>
                <span style="flex: 1; color: #8899a6;">Worker ID</span>
                <span style="color: #e7e9ea; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${status.workerId}</span>
            </div>
        `;

        // 绑定诊断工具按钮
        document.getElementById('xmatrix-btn-diagnostic').addEventListener('click', () => {
            chrome.runtime.sendMessage({ action: 'open_options' });
        });

        // 点击外部关闭
        document.addEventListener('click', function closePopup(e) {
            if (!popup.contains(e.target) && e.target.id !== 'xmatrix-float-btn') {
                popup.remove();
                document.removeEventListener('click', closePopup);
            }
        });
    }

    // ================= 【初始化】 =================

    // 等待页面加载完成后注入按钮
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createFloatButton);
    } else {
        createFloatButton();
    }

    console.log('[X-Matrix] 浮动状态按钮已注入');
})();
