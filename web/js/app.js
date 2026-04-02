/**
 * 应用入口和初始化模块
 * 负责应用启动和各模块协调
 */

import { AppState } from './state.js';
import { apiPost } from './api.js';
import { getDOM, showModal, hideModal } from './utils.js';
import { handleLogin, handleSetPassword, handleChangePassword, handleLogout, updateUserName } from './auth.js';
import { loadSessions, createSession, deleteSession, selectSession, updateSessionPathHeader, editSessionPathInHeader, editSessionTitle } from './session.js';
import { loadMessages, renderMessages, sendMessage, toggleTool } from './message.js';
import { connectSSE } from './sse.js';
import { loadModels, loadAgents, updateUserSelections } from './config.js';
import { initDragDrop, initPasteImage, addPendingFile, renderFilePreview, removePendingFile } from './upload.js';
import { initBackground } from './background.js';

// 导出全局函数（供HTML调用）
window.handleLogin = handleLogin;
window.handleSetPassword = handleSetPassword;
window.handleChangePassword = handleChangePassword;
window.handleLogout = handleLogout;
window.createSession = createSession;
window.deleteSession = deleteSession;
window.selectSession = selectSession;
window.loadMessages = loadMessages;
window.toggleTool = toggleTool;
window.removePendingFile = removePendingFile;
window.toggleAutoAbort = toggleAutoAbort;

// 登录成功回调
window.onLoginSuccess = initApp;

/**
 * 切换侧边栏
 */
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    const toggleBtn = getDOM('sidebarToggle');
    
    if (window.innerWidth <= 768) {
        sidebar.classList.toggle('show');
        if (overlay) {
            overlay.classList.toggle('show');
        }
        const isShow = sidebar.classList.contains('show');
        toggleBtn.innerHTML = isShow ? '<i class="fas fa-times"></i>' : '<i class="fas fa-bars"></i>';
    } else {
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        toggleBtn.innerHTML = isCollapsed ? '<i class="fas fa-bars"></i>' : '<i class="fas fa-times"></i>';
    }
}

/**
 * 切换自动打断设置
 */
function toggleAutoAbort(checked) {
    AppState.autoAbortBeforeSend = checked;
    localStorage.setItem('autoAbortBeforeSend', checked ? 'true' : 'false');
}

/**
 * 隐藏全局Loading遮罩层
 */
function hideGlobalLoading() {
    const loading = document.getElementById('global-loading');
    if (loading) {
        loading.classList.add('fade-out');
        setTimeout(() => {
            document.body.classList.add('loaded');
        }, 300);
    }
}

/**
 * 初始化应用
 */
export async function initApp() {
    // 先获取用户配置
    try {
        const configResult = await apiPost('/api/model/get', { user_id: AppState.userQQ });
        if (configResult) {
            AppState.userConfig.model = configResult.model || null;
            AppState.userConfig.agent = configResult.agent || null;
            AppState.userConfig.provider = configResult.provider || null;
        }
    } catch (e) {
        console.log('获取用户配置失败，使用默认值');
    }
    
    // 并行加载配置和会话
    await Promise.all([loadModels(), loadAgents()]);
    await loadSessions();
    
    // 恢复之前选中的会话
    const savedSessionId = localStorage.getItem('currentSessionId');
    if (savedSessionId && AppState.sessions.find(s => (s.session_id || s.id) === savedSessionId)) {
        await selectSession(savedSessionId);
    }
    
    // 连接SSE
    connectSSE();
    
    // 初始化自动打断设置开关状态
    const autoAbortToggle = document.getElementById('autoAbortToggle');
    if (autoAbortToggle) {
        autoAbortToggle.checked = AppState.autoAbortBeforeSend;
    }
    
    // 隐藏loading遮罩层
    hideGlobalLoading();
}

/**
 * 初始化自定义下拉框
 */
function initCustomSelects() {
    document.querySelectorAll('.custom-select').forEach(wrapper => {
        const selected = wrapper.querySelector('.select-selected');
        const itemsList = wrapper.querySelector('.select-items');
        
        selected.addEventListener('click', function(e) {
            e.stopPropagation();
            closeAllSelects(this);
            itemsList.classList.toggle('select-show');
        });
    });
}

/**
 * 关闭所有下拉框
 */
function closeAllSelects(except) {
    document.querySelectorAll('.select-items').forEach(items => {
        if (items.previousElementSibling !== except) {
            items.classList.remove('select-show');
        }
    });
}

/**
 * 初始化文本域
 */
function initTextarea() {
    const chatInput = getDOM('chatInput');
    
    chatInput.addEventListener('input', async function() {
        this.style.height = '44px';
        if (this.scrollHeight > 150) {
            this.style.height = '150px';
            this.style.overflowY = 'auto';
        } else {
            this.style.height = this.scrollHeight + 'px';
            this.style.overflowY = 'hidden';
        }
        
        // 命令提示：检测输入是否以/开头
        const value = this.value;
        if (value.startsWith('/')) {
            const filter = value.substring(1);
            const { showCommandMenu } = await import('./message.js');
            showCommandMenu(filter);
        } else {
            const { hideCommandMenu } = await import('./message.js');
            hideCommandMenu();
        }
    });
    
    chatInput.addEventListener('keydown', async function(e) {
        // Esc键隐藏命令菜单
        if (e.key === 'Escape') {
            const { hideCommandMenu } = await import('./message.js');
            hideCommandMenu();
            return;
        }
        
        // Tab键选择第一个命令
        if (e.key === 'Tab' && this.value.startsWith('/')) {
            e.preventDefault();
            const commandMenu = getDOM('commandMenu');
            const firstItem = commandMenu?.querySelector('.command-item');
            if (firstItem) {
                firstItem.click();
            }
            return;
        }
        
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            // 允许一直发送，不再检查isStreaming
            if (this.value.trim()) {
                sendMessage();
            }
        }
    });
}

/**
 * 初始化发送按钮
 */
function initSendButton() {
    getDOM('sendBtn').addEventListener('click', () => {
        // 允许一直发送
        sendMessage();
    });
}

/**
 * 初始化停止按钮
 */
function initStopButton() {
    const stopBtn = getDOM('stopBtn');
    if (stopBtn) {
        stopBtn.addEventListener('click', async () => {
            const { stopSession } = await import('./message.js');
            stopSession();
        });
    }
}

/**
 * 初始化菜单
 */
function initMenu() {
    const menuBtn = getDOM('menuBtn');
    if (menuBtn) {
        menuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const dropdown = getDOM('menuDropdown');
            dropdown.classList.toggle('show');
        });
    }
    
    document.addEventListener('click', () => {
        const dropdown = getDOM('menuDropdown');
        if (dropdown && dropdown.classList.contains('show')) {
            dropdown.classList.remove('show');
        }
    });
}

/**
 * 复制会话ID
 */
function copySessionId() {
    const sessionId = AppState.currentSession?.id;
    if (sessionId) {
        navigator.clipboard.writeText(sessionId).then(() => {
            alert('会话ID已复制: ' + sessionId);
        }).catch(err => {
            console.error('复制失败:', err);
        });
    }
    getDOM('menuDropdown').classList.remove('show');
}

/**
 * 在OpenCode Web打开
 */
function openInOpenCodeWeb() {
    const sessionId = AppState.currentSession?.id;
    const sessionPath = AppState.currentSession?.directory || 'C:\\';
    if (sessionId) {
        const pathBase = btoa(sessionPath).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
        window.open(`http://127.0.0.1:4091/${pathBase}/session/${sessionId}`, '_blank');
    }
    getDOM('menuDropdown').classList.remove('show');
}

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 先隐藏全局loading，让用户看到界面
    hideGlobalLoading();
    
    // 初始化背景动画（在登录前就显示）
    initBackground();
    
    // 初始化UI交互
    initCustomSelects();
    initTextarea();
    initSendButton();
    initStopButton();
    initDragDrop();
    initPasteImage();
    initMenu();
    
    // 监听消息流滚动
    const messageContent = getDOM('messageContent');
    messageContent.addEventListener('scroll', () => {
        const threshold = 100;
        const isAtBottom = messageContent.scrollHeight - messageContent.scrollTop - messageContent.clientHeight < threshold;
        AppState.userAtBottom = isAtBottom;
    });
    
    // 点击页面关闭下拉框和命令菜单
    document.addEventListener('click', (e) => {
        closeAllSelects();
        // 隐藏命令菜单（除非点击的是命令菜单本身）
        const commandMenu = getDOM('commandMenu');
        if (commandMenu && !commandMenu.contains(e.target)) {
            commandMenu.style.display = 'none';
        }
    });
    
    // 侧边栏切换
    getDOM('sidebarToggle').addEventListener('click', toggleSidebar);
    
    // 遮罩层点击关闭侧边栏
    const overlay = document.querySelector('.sidebar-overlay');
    if (overlay) {
        overlay.addEventListener('click', toggleSidebar);
    }
    
    // 绑定路径和标题编辑
    getDOM('sessionPathHeader').onclick = editSessionPathInHeader;
    getDOM('messageTitle').onclick = editSessionTitle;
    
    // 绑定菜单功能
    window.copySessionId = copySessionId;
    window.openInOpenCodeWeb = openInOpenCodeWeb;
    
    // 检查登录状态
    const savedQQ = localStorage.getItem('userQQ');
    if (!savedQQ) {
        showModal('loginModal');
        return;
    }
    
    AppState.userQQ = savedQQ;
    AppState.userName = savedQQ;
    updateUserName(savedQQ);
    
    // 初始化应用
    await initApp();
});