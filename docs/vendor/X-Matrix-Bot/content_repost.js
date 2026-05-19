// content_repost.js

(function() {
    'use strict';

    // 绝对边缘化定位
    const wrapperStyle = `
        position: absolute;
        right: 8px;
        bottom: 8px;
        z-index: 1000;
        display: flex;
        align-items: center;
        gap: 6px;
    `;

    // 极小、半隐藏的按钮
    const miniBtnStyle = `
        padding: 4px 10px; 
        background-color: #f91880; 
        color: #fff; 
        font-size: 12px; 
        border: none; 
        border-radius: 4px; 
        cursor: pointer;
        opacity: 0.3; /* 默认半透明隐蔽 */
        transition: opacity 0.2s;
    `;

    const gearStyle = `
        cursor: pointer;
        font-size: 14px;
        opacity: 0.3;
        transition: opacity 0.2s;
    `;

    let currentLink = '';
    chrome.storage.local.get(['dynamic_append_link'], (res) => {
        currentLink = res.dynamic_append_link || '';
    });

    async function fetchBlob(url) {
        const r = await fetch(url);
        return await r.blob();
    }

    // 核心提取逻辑
    async function doRepost(article, btn) {
        if (btn.disabled) return;
        btn.disabled = true;
        btn.innerText = '⏳';

        try {
            // 1. 提取文字并进行正则去噪
            const textEl = article.querySelector('[data-testid="tweetText"]');
            let rawTxt = textEl ? textEl.innerText : '';
            let cleanTxt = rawTxt.replace(/@\w+/g, '').replace(/Replying to/ig, '').trim();
            const finalText = cleanTxt + (currentLink ? `\n\n${currentLink}` : '');

            let mediaFiles = [];

            // 2. 提取图片
            const imgs = article.querySelectorAll('[data-testid="tweetPhoto"] img');
            for (let img of imgs) {
                let u = new URL(img.src);
                u.searchParams.set('name', 'orig');
                mediaFiles.push({ blob: await fetchBlob(u.href), ext: 'jpg', type: 'image/jpeg' });
            }

            // 3. 提取视频 (新逻辑：调用 API 解析 MP4)
            const videoEl = article.querySelector('video');
            if (videoEl) {
                btn.innerText = '⏳(视频)';
                // 从推文时间戳链接中提取 Tweet ID
                const timeLink = article.querySelector('a[href*="/status/"]');
                if (timeLink) {
                    const match = timeLink.href.match(/\/status\/(\d+)/);
                    if (match) {
                        const tweetId = match[1];
                        try {
                            // 通过开放 API 抓取底层 MP4 文件
                            const apiRes = await fetch(`https://api.vxtwitter.com/Twitter/status/${tweetId}`);
                            const data = await apiRes.json();
                            if (data && data.mediaURLs) {
                                for (let url of data.mediaURLs) {
                                    if (url.includes('.mp4')) {
                                        mediaFiles.push({ blob: await fetchBlob(url), ext: 'mp4', type: 'video/mp4' });
                                    }
                                }
                            }
                        } catch (err) {
                            console.error("视频解析失败:", err);
                        }
                    }
                }
            }

            // 4. 呼出纯净发帖框
            const composeBtn = document.querySelector('a[href="/compose/tweet"]') || document.querySelector('[data-testid="SideNav_NewTweet_Button"]');
            if (!composeBtn) throw new Error("找不到发帖按钮");
            composeBtn.click();

            await new Promise(r => setTimeout(r, 1200)); 

            const editor = document.querySelector('[data-testid="tweetTextarea_0"]');
            if (editor) {
                // 5. 注入文字
                if (finalText) {
                    editor.focus();
                    const dt = new DataTransfer();
                    dt.setData('text/plain', finalText);
                    editor.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true }));
                    await new Promise(r => setTimeout(r, 600)); 
                }
                
                // 6. 统一注入媒体文件 (图片或视频)
                if (mediaFiles.length > 0) {
                    editor.focus(); 
                    const dt = new DataTransfer();
                    mediaFiles.forEach((m, i) => dt.items.add(new File([m.blob], `media${i}.${m.ext}`, {type: m.type})));
                    editor.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true }));
                }

                // 注入完成，交还控制权
                btn.innerText = '✅';
            }
        } catch (e) {
            console.error(e);
            btn.innerText = '❌';
        }

        setTimeout(() => {
            btn.disabled = false;
            btn.innerText = '🚀';
        }, 3000);
    }

    function injectDirectButtons() {
        const articles = document.querySelectorAll('article[data-testid="tweet"]');
        articles.forEach(article => {
            if (article.style.position !== 'relative') article.style.position = 'relative';
            if (article.querySelector('.matrix-tool-wrapper')) return;

            const wrapper = document.createElement('div');
            wrapper.className = 'matrix-tool-wrapper';
            wrapper.style.cssText = wrapperStyle;

            const gear = document.createElement('span');
            gear.innerText = '⚙️';
            gear.style.cssText = gearStyle;
            gear.title = "设置附加链接";
            gear.onmouseover = () => gear.style.opacity = '1';
            gear.onmouseout = () => gear.style.opacity = '0.3';
            gear.onclick = (e) => {
                e.stopPropagation();
                const newLink = window.prompt('设置转帖末尾附加的链接（清空则不附加）：', currentLink);
                if (newLink !== null) {
                    currentLink = newLink;
                    chrome.storage.local.set({ 'dynamic_append_link': newLink });
                }
            };

            const btn = document.createElement('button');
            btn.innerText = '🚀';
            btn.className = 'my-direct-btn';
            btn.style.cssText = miniBtnStyle;
            btn.onmouseover = () => btn.style.opacity = '1';
            btn.onmouseout = () => btn.style.opacity = '0.3';
            
            btn.onclick = (e) => { 
                e.preventDefault(); 
                e.stopPropagation(); 
                doRepost(article, btn); 
            };

            wrapper.appendChild(gear);
            wrapper.appendChild(btn);
            article.appendChild(wrapper);
        });
    }

    setInterval(injectDirectButtons, 1500);

})();