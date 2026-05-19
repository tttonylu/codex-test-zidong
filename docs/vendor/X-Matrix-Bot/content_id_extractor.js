// ==============================================================================
// X-Matrix-Bot 插件 - 用户ID自动提取器 (V11.5.3)
// ==============================================================================
// 功能：
//   在 X 平台页面自动提取当前登录用户的 handle（@username）
//   并通过背景页上报到 NAS，用于 Agent 的 profile_mapping 自动配置
//
// 触发时机：
//   页面加载完成后自动执行
//
// 上报数据格式：
//   {
//     action: "report_user_id",
//     profile_id: "@handle#instanceId",
//     handle: "username",
//     url: "当前页面URL",
//     timestamp: 1234567890
//   }
// ==============================================================================

(function() {
    'use strict';

    // 防止重复注入
    if (window.__matrix_id_extractor_injected__) return;
    window.__matrix_id_extractor_injected__ = true;

    // ================= 【诊断日志】 =================
    console.log('[诊断-注入] content_id_extractor.js 已加载');
    console.log('[诊断-环境] chrome 对象:', typeof chrome);
    console.log('[诊断-环境] chrome.runtime:', typeof chrome !== 'undefined' ? typeof chrome.runtime : 'N/A');
    console.log('[诊断-环境] chrome.runtime.sendMessage:', typeof chrome !== 'undefined' && chrome.runtime ? typeof chrome.runtime.sendMessage : 'N/A');

    // NAS地址已从config.js统一管理，此处不再硬编码

    // 延迟执行，等待页面完全加载
    setTimeout(extractAndReport, 3000);

    function extractAndReport() {
        try {
            // 方法1: 从导航栏个人资料链接提取
            let handle = null;

            const profileLink = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]');
            if (profileLink && profileLink.href) {
                const match = profileLink.href.match(/x\.com\/([^\/\?]+)/);
                if (match && match[1] && match[1] !== 'i' && match[1] !== 'home') {
                    handle = match[1].toLowerCase();
                }
            }

            // 方法2: 从账号切换按钮提取
            if (!handle) {
                const accountBtn = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
                if (accountBtn) {
                    const text = accountBtn.innerText || '';
                    const match = text.match(/@([\w_]+)/i);
                    if (match) {
                        handle = match[1].toLowerCase();
                    }
                }
            }

            // 方法3: 从页面 meta 或脚本数据提取
            if (!handle) {
                const scripts = document.querySelectorAll('script');
                for (const script of scripts) {
                    const text = script.textContent || '';
                    // 查找 screen_name
                    const match = text.match(/"screen_name":"([^"]+)"/);
                    if (match) {
                        handle = match[1].toLowerCase();
                        break;
                    }
                }
            }

            // 方法4: 从 URL 路径提取（如果在个人主页）
            if (!handle) {
                const path = window.location.pathname;
                const match = path.match(/^\/([\w_]+)(?:\/|$)/);
                if (match && match[1] && !['home', 'explore', 'notifications', 'messages', 'i', 'search'].includes(match[1])) {
                    handle = match[1].toLowerCase();
                }
            }

            if (!handle) {
                console.log('[ID提取器] 未能提取到用户ID');
                return;
            }

            // 获取实例ID（与 content_chat.js / content_follow.js 保持一致）
            let instanceId = sessionStorage.getItem('matrix_instance_id');
            if (!instanceId) {
                instanceId = Math.random().toString(36).substr(2, 9);
                sessionStorage.setItem('matrix_instance_id', instanceId);
            }

            const profileId = '@' + handle + '#' + instanceId;

            // 上报到 NAS
            const payload = {
                action: "report_user_id",
                profile_id: profileId,
                handle: handle,
                url: window.location.href,
                timestamp: Math.floor(Date.now() / 1000)
            };

            // 通过 background.js 上报（避免 Mixed Content）
            try {
                chrome.runtime.sendMessage(payload, (response) => {
                    if (chrome.runtime.lastError) {
                        console.log('[ID提取器] Service Worker 未就绪:', chrome.runtime.lastError.message);
                        // 稍后重试
                        setTimeout(() => directReport(payload), 5000);
                    } else {
                        console.log('[ID提取器] 上报成功:', response);
                    }
                });
            } catch (e) {
                console.log('[ID提取器] 上报异常:', e);
                setTimeout(() => directReport(payload), 5000);
            }

            // 同时在页面显示提取到的ID（方便调试）
            showExtractedId(handle, profileId);

        } catch (e) {
            console.error('[ID提取器] 错误:', e);
        }
    }

    function directReport(payload) {
        // 通过 background.js 上报（避免 HTTPS 页面的 Mixed Content 问题）
        try {
            chrome.runtime.sendMessage({
                action: "report_user_id",
                profile_id: payload.profile_id,
                handle: payload.handle,
                url: payload.url,
                timestamp: payload.timestamp
            }, (response) => {
                if (chrome.runtime.lastError) {
                    console.log('[ID提取器] 上报失败:', chrome.runtime.lastError);
                } else {
                    console.log('[ID提取器] 上报成功:', response);
                }
            });
        } catch (e) {
            console.log('[ID提取器] 上报失败:', e);
        }
    }

    function showExtractedId(handle, profileId) {
        // 如果页面上已有显示元素，更新它
        let el = document.getElementById('matrix-id-extractor-info');
        if (!el) {
            el = document.createElement('div');
            el.id = 'matrix-id-extractor-info';
            el.style.cssText = `
                position: fixed;
                top: 8px;
                right: 8px;
                background: rgba(0,0,0,0.7);
                color: #00ba7c;
                padding: 3px 6px;
                border-radius: 4px;
                font-size: 10px;
                font-family: monospace;
                z-index: 999999;
                border: 1px solid rgba(0,186,124,0.4);
                max-width: 140px;
                word-break: break-all;
                line-height: 1.3;
                cursor: pointer;
            `;
            el.title = '点击隐藏';
            el.onclick = () => { if(el) el.style.display='none'; };
            document.body.appendChild(el);
        }

        el.innerHTML = `
            <div style="font-weight:bold;">🔍 @${handle}</div>
            <div style="color:#1d9bf0;font-size:9px;">✅ 已上报</div>
        `;

        // 5秒后淡出为几乎透明
        setTimeout(() => {
            if (el) {
                el.style.transition = 'opacity 2s';
                el.style.opacity = '0.15';
            }
        }, 5000);
    }

})();
