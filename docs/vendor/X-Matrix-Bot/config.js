// X-Matrix-Bot 统一配置中心 (V11.5.4 配置化版)
// 兼容 Content Script 页面环境和 Service Worker 环境
(function(global) {
    'use strict';

    const DEFAULTS = {
        NAS_5000: 'http://192.168.0.100:5678'
        // V11.6.0: 移除 NAS_5050，所有服务统一使用 5678 端口
    };

    let cfg = { ...DEFAULTS };
    let loaded = false;

    const storage = (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.sync)
        ? chrome.storage.sync
        : null;

    function loadFromStorage() {
        if (!storage) {
            loaded = true;
            console.log('[Config] 无storage API，使用默认配置');
            return;
        }
        storage.get(['matrix_cfg_NAS_5000'], function(result) {
            if (chrome.runtime.lastError) {
                console.log('[Config] storage读取失败:', chrome.runtime.lastError.message);
            } else {
                if (result.matrix_cfg_NAS_5000) cfg.NAS_5000 = result.matrix_cfg_NAS_5000;
            }
            loaded = true;
            console.log('[Config] 配置加载完成:', JSON.stringify(cfg));
        });
    }

    const api = {
        get: function(key) { return cfg[key] || DEFAULTS[key]; },
        getNAS5000: function() { return this.get('NAS_5000'); },
        set: function(key, value, cb) {
            cfg[key] = value;
            if (storage) {
                storage.set({ ['matrix_cfg_' + key]: value }, function() {
                    if (cb) cb(chrome.runtime.lastError);
                });
            } else if (cb) {
                cb(null);
            }
        },
        getAll: function() { return { ...cfg }; },
        isLoaded: function() { return loaded; }
    };

    // 暴露到全局
    if (typeof global !== 'undefined') {
        global.__MATRIX_CONFIG = api;
    }

    loadFromStorage();
})(typeof self !== 'undefined' ? self : typeof window !== 'undefined' ? window : typeof global !== 'undefined' ? global : this);
