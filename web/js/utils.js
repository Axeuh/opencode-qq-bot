/**
 * 工具函数模块
 * 提供通用的工具函数（优化版）
 */

// ============ DOM缓存 ============

const DOMCache = {};

/**
 * 获取DOM元素（带缓存）
 * @param {string} id - 元素ID
 * @returns {HTMLElement|null}
 */
export function getDOM(id) {
    if (!DOMCache[id]) {
        DOMCache[id] = document.getElementById(id);
    }
    return DOMCache[id];
}

/**
 * 清除DOM缓存
 * @param {string} id - 元素ID（可选，不传则清除全部）
 */
export function clearDOMCache(id) {
    if (id) {
        delete DOMCache[id];
    } else {
        Object.keys(DOMCache).forEach(key => delete DOMCache[key]);
    }
}

// ============ HTML转义 ============

// 缓存escapeHtml的div元素
const escapeDiv = document.createElement('div');

/**
 * HTML转义
 * @param {string} text - 原始文本
 * @returns {string} 转义后的文本
 */
export function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    escapeDiv.textContent = String(text);
    return escapeDiv.innerHTML;
}

// ============ 时间格式化 ============

/**
 * 格式化时间
 * @param {string|number} isoString - ISO时间字符串或时间戳
 * @returns {string} 格式化后的时间字符串
 */
export function formatTime(isoString) {
    if (!isoString) return '';
    
    // 处理数字时间戳
    let timestamp = isoString;
    if (typeof isoString === 'number') {
        timestamp = isoString < 1e12 ? isoString * 1000 : isoString;
    }
    
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
    if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
    if (diff < 604800000) return Math.floor(diff / 86400000) + '天前';
    
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

// ============ Markdown格式化 ============

// 标记marked是否已配置
let markedConfigured = false;

/**
 * 格式化Markdown
 * @param {string} text - Markdown文本
 * @returns {string} HTML字符串
 */
export function formatMarkdown(text) {
    if (!text) return '';
    
    // 只配置一次marked
    if (typeof marked !== 'undefined' && !markedConfigured) {
        marked.setOptions({
            highlight: function(code, lang) {
                if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {}
                }
                if (typeof hljs !== 'undefined') {
                    try {
                        return hljs.highlightAuto(code).value;
                    } catch (e) {}
                }
                return code;
            },
            breaks: true,
            gfm: true
        });
        markedConfigured = true;
    }
    
    if (typeof marked !== 'undefined') {
        return '<div class="markdown-content">' + marked.parse(text) + '</div>';
    }
    
    // 回退：简单格式化
    return '<div class="markdown-content">' + text
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>') + '</div>';
}

// ============ 文件大小格式化 ============

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string} 格式化后的大小字符串
 */
export function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ============ 模态框工具 ============

/**
 * 显示模态框
 * @param {string} id - 模态框元素ID
 */
export function showModal(id) {
    const el = getDOM(id);
    if (el) el.style.display = 'flex';
}

/**
 * 隐藏模态框
 * @param {string} id - 模态框元素ID
 */
export function hideModal(id) {
    const el = getDOM(id);
    if (el) el.style.display = 'none';
}

// ============ 渲染节流 ============

export const RENDER_THROTTLE = 50;

/**
 * 调度渲染（节流）
 * @param {Function} renderFn - 渲染函数
 * @param {object} state - 状态对象（需要 renderPending 和 lastRenderTime 属性）
 */
export function scheduleRender(renderFn, state) {
    const now = Date.now();
    const timeSinceLastRender = now - state.lastRenderTime;
    
    if (timeSinceLastRender >= RENDER_THROTTLE) {
        state.lastRenderTime = now;
        renderFn();
    } else if (!state.renderPending) {
        state.renderPending = true;
        requestAnimationFrame(() => {
            state.renderPending = false;
            state.lastRenderTime = Date.now();
            renderFn();
        });
    }
}

// ============ 文件读取 ============

/**
 * 读取文件为DataURL
 * @param {File} file - 文件对象
 * @returns {Promise<string>} DataURL字符串
 */
export function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

// ============ 其他工具 ============

/**
 * 复制文本到剪贴板
 * @param {string} text - 要复制的文本
 * @returns {Promise<void>}
 */
export async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        console.error('复制失败:', err);
        return false;
    }
}

/**
 * 防抖函数
 * @param {Function} fn - 要防抖的函数
 * @param {number} delay - 延迟时间（毫秒）
 * @returns {Function}
 */
export function debounce(fn, delay = 300) {
    let timer = null;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * 节流函数
 * @param {Function} fn - 要节流的函数
 * @param {number} interval - 间隔时间（毫秒）
 * @returns {Function}
 */
export function throttle(fn, interval = 100) {
    let lastTime = 0;
    return function(...args) {
        const now = Date.now();
        if (now - lastTime >= interval) {
            lastTime = now;
            fn.apply(this, args);
        }
    };
}