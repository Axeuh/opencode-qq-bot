/**
 * 会话管理模块
 * 处理会话列表、创建、删除、切换等功能
 */

import { AppState, ensureSessionState } from './state.js';
import { apiGet, apiPost } from './api.js';
import { escapeHtml, formatTime, getDOM } from './utils.js';

/**
 * 加载会话列表
 */
export async function loadSessions() {
    try {
        const userQQ = AppState.userQQ;
        
        const result = await apiPost('/api/session/list', { user_id: userQQ });
        
        if (result && Array.isArray(result.sessions)) {
            AppState.sessions = result.sessions.map(s => ({
                id: s.session_id || s.id,
                session_id: s.session_id || s.id,
                title: s.title || '未命名会话',
                created_at: s.created_at || Date.now() / 1000,
                last_accessed: s.last_accessed || s.updated_at || Date.now() / 1000,
                directory: s.directory,
                tokens: s.tokens || null
            }));
        }
        
        if (!AppState.sessions) {
            AppState.sessions = [];
        }
        
        // 为每个会话获取最后一条消息预览
        await Promise.all(AppState.sessions.slice(0, 20).map(async session => {
            const sessionId = session.session_id;
            try {
                const messages = await apiGet(`/api/opencode/sessions/${sessionId}/messages?limit=1`);
                if (messages && messages.length > 0) {
                    const lastMsg = messages[messages.length - 1];
                    let preview = '';
                    if (lastMsg.parts && lastMsg.parts.length > 0) {
                        const textParts = lastMsg.parts.filter(p => p.type === 'text');
                        preview = textParts.map(p => p.text || '').join('').substring(0, 50);
                    }
                    if (!preview && lastMsg.info?.role) {
                        preview = lastMsg.info.role === 'user' ? '用户消息' : 'AI回复';
                    }
                    preview = preview.replace(/^\[QQ用户[^}\]]*\}\s*/, '').substring(0, 30);
                    session.last_message = preview || '暂无消息';
                } else {
                    session.last_message = '暂无消息';
                }
            } catch (e) {
                session.last_message = '暂无消息';
            }
        }));
        
        renderSessions();
    } catch (error) {
        console.error('加载会话列表失败:', error);
    }
}

/**
 * 渲染会话列表
 */
export function renderSessions() {
    const container = getDOM('sessionList');
    container.innerHTML = '';
    
    if (AppState.sessions.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 20px; color: var(--text-sub); font-size: 13px;">
                暂无会话<br>点击下方按钮新建
            </div>
        `;
        return;
    }
    
    // 按时间降序排序
    const sortedSessions = [...AppState.sessions].sort((a, b) => {
        const timeA = a.last_accessed || a.updated_at || a.time?.updated || 0;
        const timeB = b.last_accessed || b.updated_at || b.time?.updated || 0;
        const tsA = typeof timeA === 'number' ? (timeA < 1e12 ? timeA * 1000 : timeA) : new Date(timeA).getTime();
        const tsB = typeof timeB === 'number' ? (timeB < 1e12 ? timeB * 1000 : timeB) : new Date(timeB).getTime();
        return tsB - tsA;
    });
    
    sortedSessions.forEach(session => {
        const sessionId = session.session_id || session.id;
        const item = document.createElement('div');
        item.className = 'session-item' + (AppState.currentSession?.id === sessionId ? ' active' : '');
        item.dataset.sessionId = sessionId;
        
        const time = session.last_accessed || session.updated_at || session.time?.updated ? 
            formatTime(session.last_accessed || session.updated_at || session.time?.updated) : '';
        
        let preview = session.last_message;
        
        // 当前选中会话实时更新预览
        if (AppState.currentSession?.id === sessionId && AppState.parts[sessionId]) {
            const parts = AppState.parts[sessionId];
            const msgs = AppState.messages[sessionId] || [];
            if (msgs.length > 0) {
                const lastMsg = msgs[msgs.length - 1];
                const msgParts = Object.values(parts).filter(p => p.messageID === lastMsg.id && p.type === 'text');
                if (msgParts.length > 0) {
                    preview = msgParts.map(p => p.text || '').join('');
                    preview = preview.replace(/^\[QQ用户[^}\]]*\}\s*/, '').substring(0, 30);
                } else if (lastMsg.role === 'user') {
                    preview = '用户消息...';
                } else if (AppState.isStreaming) {
                    preview = '思考中...';
                }
            }
        }
        
        if (preview) {
            preview = preview.replace(/^\[QQ用户[^}\]]*\}\s*/, '').substring(0, 30);
        }
        if (!preview) preview = '暂无消息';

        item.innerHTML = `
            <div class="session-header">
                <span class="session-title">${escapeHtml(session.title || '新会话')}</span>
                <span class="session-time">${time}</span>
            </div>
            <div class="session-preview">${escapeHtml(preview)}</div>
            <button class="session-delete" title="删除会话" onclick="event.stopPropagation(); window.deleteSession('${sessionId}')">
                <i class="fas fa-trash"></i>
            </button>
        `;
        
        item.addEventListener('click', () => window.selectSession(sessionId));
        container.appendChild(item);
    });
}

/**
 * 创建新会话
 */
export async function createSession() {
    try {
        const result = await apiPost('/api/session/new', { user_id: AppState.userQQ });
        if (result.success && result.session) {
            const session = result.session;
            session.session_id = session.session_id || session.id;
            AppState.sessions.unshift(session);
            renderSessions();
            window.selectSession(session.session_id);
        } else {
            throw new Error(result.error || '创建会话失败');
        }
    } catch (error) {
        console.error('创建会话失败:', error);
        alert('创建会话失败: ' + error.message);
    }
}

/**
 * 删除会话
 * @param {string} sessionId - 会话ID
 */
export async function deleteSession(sessionId) {
    if (!confirm('确定要删除这个会话吗？')) return;
    
    try {
        const result = await apiPost('/api/session/delete', { user_id: AppState.userQQ, session_id: sessionId });
        if (result.success) {
            AppState.sessions = AppState.sessions.filter(s => (s.session_id || s.id) !== sessionId);
        } else {
            throw new Error(result.error || '删除会话失败');
        }
        
        if (AppState.currentSession?.id === sessionId) {
            AppState.currentSession = null;
            getDOM('messageHeader').style.display = 'none';
            getDOM('messageContent').innerHTML = `
                <div class="empty-state" id="emptyState">
                    <i class="fas fa-comments"></i>
                    <p>选择一个会话开始聊天</p>
                    <p style="font-size: 12px; margin-top: 8px;">或点击「新建会话」开始新对话</p>
                </div>
            `;
            getDOM('chatInput').disabled = true;
            getDOM('sendBtn').disabled = true;
        }
        
        renderSessions();
    } catch (error) {
        console.error('删除会话失败:', error);
        alert('删除会话失败: ' + error.message);
    }
}

/**
 * 选择会话
 * @param {string} sessionId - 会话ID
 */
export async function selectSession(sessionId) {
    if (!sessionId) {
        console.error('selectSession: sessionId is undefined');
        return;
    }
    
    // 更新选中状态
    AppState.currentSession = AppState.sessions.find(s => (s.session_id || s.id) === sessionId);
    if (AppState.currentSession) {
        AppState.currentSession.id = sessionId;
    }
    
    localStorage.setItem('currentSessionId', sessionId);
    
    // 更新 UI
    document.querySelectorAll('.session-item').forEach(item => {
        item.classList.toggle('active', item.dataset.sessionId === sessionId);
    });
    
    // 切换后端的当前会话
    try {
        await apiPost('/api/session/switch', { user_id: AppState.userQQ, session_id: sessionId });
    } catch (e) {
        console.warn('切换后端会话失败:', e);
    }
    
    // 获取当前会话的路径
    try {
        const pathResult = await apiPost('/api/directory/get', { user_id: AppState.userQQ });
        if (pathResult && pathResult.success) {
            AppState.currentSession.directory = pathResult.directory || '';
        }
    } catch (e) {
        console.log('获取会话路径失败:', e);
    }
    
    // 更新会话标题栏的路径显示
    updateSessionPathHeader();
    
    // 启用输入
    getDOM('chatInput').disabled = false;
    getDOM('sendBtn').disabled = false;
    
    // 加载消息
    await window.loadMessages(sessionId);
}

/**
 * 更新会话路径显示
 */
export function updateSessionPathHeader() {
    const pathElement = getDOM('sessionPathHeader');
    if (!pathElement) return;
    
    if (AppState.currentSession) {
        const sessionPath = AppState.currentSession.directory || '';
        pathElement.textContent = sessionPath || '默认路径';
        pathElement.title = '点击编辑路径';
        pathElement.style.display = 'inline-block';
    } else {
        pathElement.style.display = 'none';
    }
}

/**
 * 编辑会话路径
 */
export async function editSessionPathInHeader() {
    const pathElement = getDOM('sessionPathHeader');
    if (!pathElement || !AppState.currentSession) return;
    
    const sessionId = AppState.currentSession.id;
    const currentPath = AppState.currentSession.directory || '';
    const originalText = pathElement.textContent;
    
    let restored = false;
    
    const restoreSpan = (text) => {
        if (restored) return;
        restored = true;
        
        const span = document.createElement('span');
        span.id = 'sessionPathHeader';
        span.className = 'session-path-header';
        span.style.cssText = `
            display: inline-block;
            margin-left: 12px;
            font-size: 12px;
            color: #888;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 40%;
            min-width: 50px;
            flex: 0 1 auto;
            cursor: pointer;
        `;
        span.title = '点击编辑路径';
        span.textContent = text;
        span.onclick = editSessionPathInHeader;
        
        if (input.parentNode) {
            input.replaceWith(span);
        }
    };
    
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentPath;
    input.style.cssText = `
        font-size: 12px;
        padding: 2px 6px;
        border: 1px solid var(--primary-blue);
        border-radius: 4px;
        background: white;
        color: #333;
        max-width: 40%;
        min-width: 100px;
        flex: 0 1 auto;
        margin-left: 12px;
    `;
    
    pathElement.replaceWith(input);
    input.focus();
    input.select();
    
    input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const newPath = input.value.trim();
            const sessionId = AppState.currentSession ? AppState.currentSession.id : null;
            try {
                const result = await apiPost('/api/directory/set', {
                    user_id: AppState.userQQ,
                    directory: newPath,
                    session_id: sessionId
                });
                if (result.success && AppState.currentSession) {
                    AppState.currentSession.directory = result.directory || newPath;
                }
                restoreSpan(result.directory || newPath || '默认路径');
            } catch (error) {
                console.error('保存路径失败:', error);
                restoreSpan(originalText);
            }
        } else if (e.key === 'Escape') {
            e.preventDefault();
            restoreSpan(originalText);
        }
    });
    
    input.addEventListener('blur', () => {
        setTimeout(() => {
            if (!restored) {
                const newPath = input.value.trim();
                const sessionId = AppState.currentSession ? AppState.currentSession.id : null;
                apiPost('/api/directory/set', {
                    user_id: AppState.userQQ,
                    directory: newPath,
                    session_id: sessionId
                }).then(result => {
                    if (result.success && AppState.currentSession) {
                        AppState.currentSession.directory = result.directory || newPath;
                    }
                    restoreSpan(result.directory || newPath || '默认路径');
                }).catch(error => {
                    console.error('保存路径失败:', error);
                    restoreSpan(originalText);
                });
            }
        }, 100);
    });
}

/**
 * 编辑会话标题
 */
export async function editSessionTitle() {
    const titleElement = getDOM('messageTitle');
    if (!titleElement || !AppState.currentSession) return;
    
    const currentTitle = AppState.currentSession.title || '';
    const originalText = titleElement.textContent;
    let restored = false;
    
    const restoreDiv = (text) => {
        if (restored) return;
        restored = true;
        
        const div = document.createElement('div');
        div.id = 'messageTitle';
        div.className = 'message-header-title';
        div.style.cssText = 'cursor: pointer;';
        div.title = '点击编辑标题';
        div.textContent = text;
        div.onclick = editSessionTitle;
        
        input.replaceWith(div);
    };
    
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentTitle;
    input.style.cssText = `
        font-size: 16px;
        font-weight: 600;
        padding: 4px 8px;
        border: 1px solid var(--primary-blue);
        border-radius: 4px;
        background: white;
        min-width: 200px;
        max-width: 400px;
    `;
    
    titleElement.replaceWith(input);
    input.focus();
    input.select();
    
    input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const newTitle = input.value.trim();
            const sessionId = AppState.currentSession.id;
            
            if (!newTitle) {
                restoreDiv(originalText);
                return;
            }
            
            try {
                const botResult = await apiPost('/api/session/title', {
                    user_id: AppState.userQQ,
                    session_id: sessionId,
                    title: newTitle
                });
                
                // 同步到OpenCode
                try {
                    await fetch(`http://127.0.0.1:4091/session/${sessionId}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title: newTitle })
                    });
                } catch (ocError) {
                    console.warn('同步到OpenCode失败:', ocError);
                }
                
                if (botResult.success && AppState.currentSession) {
                    AppState.currentSession.title = newTitle;
                    const session = AppState.sessions.find(s => (s.session_id || s.id) === sessionId);
                    if (session) session.title = newTitle;
                    renderSessions();
                }
                restoreDiv(newTitle);
            } catch (error) {
                console.error('保存标题失败:', error);
                restoreDiv(originalText);
            }
        } else if (e.key === 'Escape') {
            e.preventDefault();
            restoreDiv(originalText);
        }
    });
    
    input.addEventListener('blur', () => {
        setTimeout(() => {
            if (!restored) {
                restoreDiv(originalText);
            }
        }, 100);
    });
}