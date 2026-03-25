/**
 * 消息渲染模块
 * 处理消息的加载、渲染和发送
 */

import { AppState, ensureSessionState, RENDER_THROTTLE } from './state.js';
import { apiGet, apiPost } from './api.js';
import { escapeHtml, formatTime, formatMarkdown, getDOM, scheduleRender } from './utils.js';
import { renderSessions } from './session.js';

/**
 * 加载消息
 * @param {string} sessionId - 会话ID
 */
export async function loadMessages(sessionId) {
    if (!sessionId) {
        console.error('loadMessages: sessionId is undefined');
        return;
    }
    
    try {
        const allMessages = await apiGet(`/api/opencode/sessions/${sessionId}/messages?limit=20`);
        const messages = allMessages || [];
        
        // 保存临时用户消息
        const existingMessages = AppState.messages[sessionId] || [];
        const tempUserMsg = existingMessages.find(m => m.id.startsWith('temp_user_'));
        
        // 转换并存储
        AppState.messages[sessionId] = messages.map(msg => ({
            id: msg.info?.id || msg.id,
            role: msg.info?.role || msg.role,
            modelID: msg.info?.modelID,
            agent: msg.info?.agent,
            time: msg.info?.time || { created: msg.created_at }
        }));
        
        // 保留临时用户消息
        if (tempUserMsg && !messages.find(m => (m.info?.id || m.id) === tempUserMsg.id)) {
            AppState.messages[sessionId].push(tempUserMsg);
        }
        
        // 初始化parts
        if (!AppState.parts[sessionId]) AppState.parts[sessionId] = {};
        messages.forEach(msg => {
            const msgID = msg.info?.id || msg.id;
            if (msg.parts) {
                msg.parts.forEach(part => {
                    if (part.id) {
                        AppState.parts[sessionId][part.id] = {
                            ...part,
                            messageID: msgID
                        };
                    }
                });
            }
        });
        
        renderMessages();
    } catch (error) {
        console.error('加载消息失败:', error);
    }
}

/**
 * 渲染所有消息
 */
export function renderMessages() {
    const container = getDOM('messageContent');
    const header = getDOM('messageHeader');
    const titleEl = getDOM('messageTitle');
    const subEl = getDOM('messageSub');
    const sessionId = AppState.currentSession?.id;
    
    if (!sessionId) {
        if (header) header.style.display = 'flex';
        if (titleEl) titleEl.textContent = '请选择会话';
        if (subEl) subEl.textContent = '';
        const tokenCountEl = getDOM('tokenCount');
        if (tokenCountEl) tokenCountEl.textContent = '0';
        container.innerHTML = `
            <div class="empty-state" id="emptyState">
                <i class="fas fa-comments"></i>
                <p>选择一个会话开始聊天</p>
                <p style="font-size: 12px; margin-top: 8px;">或点击「新建会话」开始新对话</p>
            </div>
        `;
        return;
    }
    
    // 更新标题栏
    if (header) header.style.display = 'flex';
    const session = AppState.sessions.find(s => s.id === sessionId || s.session_id === sessionId);
    if (titleEl) titleEl.textContent = session?.title || '新会话';
    const msgCount = (AppState.messages[sessionId] || []).length;
    if (subEl) subEl.textContent = `${msgCount} 条消息`;
    
    // 显示token数量
    const tokens = session?.tokens || {};
    const totalTokens = tokens.total || ((tokens.input || 0) + (tokens.output || 0) + (tokens.reasoning || 0));
    const tokenCountEl = getDOM('tokenCount');
    if (tokenCountEl) tokenCountEl.textContent = totalTokens.toLocaleString();
    
    const messages = AppState.messages[sessionId] || [];
    const parts = AppState.parts[sessionId] || {};
    
    // 按messageID分组parts
    const partsByMessage = {};
    Object.values(parts).forEach(part => {
        if (part.messageID) {
            if (!partsByMessage[part.messageID]) partsByMessage[part.messageID] = [];
            partsByMessage[part.messageID].push(part);
        }
    });
    
    // 按时间排序消息
    messages.sort((a, b) => {
        const timeA = a.time?.created ? new Date(a.time.created).getTime() : 0;
        const timeB = b.time?.created ? new Date(b.time.created).getTime() : 0;
        return timeA - timeB;
    });
    
    container.innerHTML = '';
    
    if (messages.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-comment-dots"></i>
                <p>开始新的对话吧</p>
            </div>
        `;
        return;
    }
    
    // 使用DocumentFragment优化渲染
    const fragment = document.createDocumentFragment();
    messages.forEach(msg => {
        const msgParts = partsByMessage[msg.id] || [];
        const element = renderMessage(msg, msgParts);
        if (element) fragment.appendChild(element);
    });
    container.appendChild(fragment);
    
    // 检查是否需要显示"思考中..."
    if (AppState.isStreaming && messages.length > 0) {
        const lastMsg = messages[messages.length - 1];
        const lastMsgRole = lastMsg.role || lastMsg.info?.role;
        
        let showThinking = false;
        if (lastMsgRole === 'user') {
            showThinking = true;
        } else if (lastMsgRole === 'assistant') {
            const lastMsgParts = partsByMessage[lastMsg.id] || [];
            const hasContent = lastMsgParts.some(p => p.text && p.text.trim());
            if (!hasContent) {
                showThinking = true;
            }
        }
        
        if (showThinking) {
            const thinkingEl = document.createElement('div');
            thinkingEl.className = 'msg-ai-wrap thinking-placeholder';
            thinkingEl.id = 'thinking-placeholder';
            thinkingEl.innerHTML = `
                <img src="https://q1.qlogo.cn/g?b=qq&nk=3938121220&s=100" alt="AI" class="ai-avatar">
                <div class="ai-content">
                    <div class="ai-thinking">
                        <span class="thinking-dots">
                            <span class="dot"></span>
                            <span class="dot"></span>
                            <span class="dot"></span>
                        </span>
                        <span class="thinking-text">思考中</span>
                    </div>
                </div>
            `;
            container.appendChild(thinkingEl);
        }
    }
    
    // 只有用户在底部时才自动滚动
    if (AppState.userAtBottom) {
        container.style.scrollBehavior = 'auto';
        container.scrollTop = container.scrollHeight;
        container.style.scrollBehavior = 'smooth';
    }
    
    // 更新会话列表预览
    renderSessions();
}

/**
 * 渲染单条消息
 */
function renderMessage(msg, parts = []) {
    const role = msg.role || msg.info?.role;
    if (role === 'user') {
        return renderUserMessage(msg);
    } else if (role === 'assistant') {
        return renderAIMessage(msg, parts);
    }
    return null;
}

/**
 * 渲染用户消息
 */
function renderUserMessage(msg) {
    const wrap = document.createElement('div');
    wrap.className = 'msg-user-wrap';
    wrap.dataset.messageId = msg.id;
    
    // 从state获取内容
    let content = '';
    const sessionId = AppState.currentSession?.id;
    
    if (sessionId && AppState.parts[sessionId]) {
        const msgParts = Object.values(AppState.parts[sessionId])
            .filter(p => p.messageID === msg.id);
        content = msgParts.map(p => p.text || '').join('');
    }
    if (!content && msg.parts && Array.isArray(msg.parts)) {
        content = msg.parts.map(p => p.text || '').join('');
    }
    if (!content) content = msg.content || '';
    
    // 删除前缀标签
    const prefixPattern = /^<Axeuh_bot>\s*\n?\s*\{[\s\S]*?\}\s*\n?\s*<\/Axeuh_bot>\s*\n?/;
    content = content.replace(prefixPattern, '');
    content = content.replace(/<ultrawork-mode>[\s\S]*?<\/ultrawork-mode>/gi, '');
    
    const modelInfo = msg.modelID || AppState.selectedModel || '';
    const agentInfo = msg.agent || AppState.selectedAgent || '';
    const time = msg.time?.created ? formatTime(new Date(msg.time.created).toISOString()) : '';
    
    wrap.innerHTML = `
        <div class="msg-user-bubble">${escapeHtml(content).replace(/\n/g, '<br>')}</div>
        <div class="msg-user-info">${modelInfo} | ${agentInfo} | ${time}</div>
    `;
    
    return wrap;
}

/**
 * 渲染AI消息
 */
function renderAIMessage(msg, parts = []) {
    const wrap = document.createElement('div');
    wrap.className = 'msg-ai-wrap';
    wrap.dataset.messageId = msg.id;
    
    wrap.innerHTML = `
        <img src="https://q1.qlogo.cn/g?b=qq&nk=3938121220&s=100" alt="AI" class="ai-avatar">
        <div class="ai-content"></div>
    `;
    
    const contentEl = wrap.querySelector('.ai-content');
    
    if (parts.length === 0 && msg.parts && Array.isArray(msg.parts)) {
        parts = msg.parts;
    }
    
    if (parts.length > 0) {
        parts.forEach(part => {
            const el = renderMessagePart(part);
            if (el) contentEl.appendChild(el);
        });
    } else if (msg.content) {
        const textEl = document.createElement('div');
        textEl.className = 'ai-text';
        textEl.innerHTML = formatMarkdown(msg.content);
        contentEl.appendChild(textEl);
    } else {
        return null;
    }
    
    return wrap;
}

/**
 * 渲染消息part
 */
function renderMessagePart(part) {
    switch (part.type) {
        case 'text':
            const textEl = document.createElement('div');
            textEl.className = 'ai-text';
            if (part.id) textEl.dataset.partId = part.id;
            textEl.innerHTML = formatMarkdown(part.text);
            return textEl;
            
        case 'reasoning':
        case 'thought':
            const thoughtEl = document.createElement('div');
            thoughtEl.className = 'thought-block';
            if (part.id) thoughtEl.dataset.partId = part.id;
            const thoughtText = document.createElement('div');
            thoughtText.className = 'thought-text';
            thoughtText.textContent = part.text || part.content || '';
            thoughtEl.appendChild(thoughtText);
            return thoughtEl;
            
        case 'tool':
            return renderToolPart(part);
            
        case 'tool_call':
            return renderToolCard(part);
            
        case 'tool_result':
            return renderToolResult(part);
            
        default:
            return null;
    }
}

/**
 * 渲染工具调用part
 */
function renderToolPart(part) {
    const card = document.createElement('div');
    card.className = 'tool-card';
    
    const toolName = part.tool || 'tool';
    const state = part.state || {};
    const status = state.status || 'pending';
    const input = state.input || {};
    const output = state.output || '';
    
    // 根据工具类型渲染
    if (toolName === 'bash') {
        card.classList.add('expanded');
        const command = input.command || input.cmd || '';
        const description = input.description || '';
        const exitCode = state.exitCode !== undefined ? state.exitCode : '0';
        const is_success = exitCode === 0 || exitCode === '0';
        
        const displayTitle = description || command;
        const shortTitle = displayTitle.length > 50 ? displayTitle.substring(0, 47) + '...' : displayTitle;
        
        card.innerHTML = `
            <div class="tool-header" onclick="window.toggleTool(this)" title="${escapeHtml(displayTitle)}">
                <div><i class="fas fa-terminal tool-icon" style="color:#333;"></i>bash · ${escapeHtml(shortTitle)}</div>
                <i class="fas fa-chevron-down tool-toggle-icon"></i>
            </div>
            <div class="tool-body">
                <div class="bash-cmd">$ ${escapeHtml(command)}
${escapeHtml(String(output).replace(/Exit Code:\s*\d+.*$/s, '').trim().substring(0, 2000))}${String(output).length > 2000 ? '\n...(输出过长已截断)' : ''}</div>
                <div class="bash-status" style="color: ${is_success ? '#28a745' : '#dc3545'};">
                    <i class="fas ${is_success ? 'fa-check-circle' : 'fa-times-circle'}"></i> 
                    Exit Code: ${exitCode} ${is_success ? '(Success)' : '(Failed)'}
                </div>
            </div>
        `;
    } else {
        // 通用工具卡片
        let iconClass = 'fa-cog';
        if (toolName.includes('read') || toolName.includes('file')) iconClass = 'fa-file-code';
        else if (toolName.includes('edit') || toolName.includes('write')) iconClass = 'fa-edit';
        else if (toolName.includes('grep')) iconClass = 'fa-search';
        
        card.innerHTML = `
            <div class="tool-header" onclick="window.toggleTool(this)">
                <div><i class="fas ${iconClass} tool-icon"></i>${escapeHtml(toolName)}</div>
                <i class="fas fa-chevron-down tool-toggle-icon"></i>
            </div>
            <div class="tool-body">
                <pre style="margin:0;white-space:pre-wrap;font-size:12px;color:#666;background:#f8fafc;padding:8px;border-radius:6px;max-height:150px;overflow-y:auto;">${escapeHtml(JSON.stringify(input, null, 2))}</pre>
                ${output ? `<div class="bash-cmd" style="margin-top:8px;max-height:200px;overflow-y:auto;">${escapeHtml(String(output).substring(0, 2000))}${String(output).length > 2000 ? '...' : ''}</div>` : ''}
            </div>
        `;
    }
    
    return card;
}

/**
 * 渲染工具卡片
 */
function renderToolCard(part) {
    const card = document.createElement('div');
    card.className = 'tool-card';
    
    const toolName = part.name || part.tool_name || 'tool';
    const toolInput = part.input || part.arguments || {};
    
    card.innerHTML = `
        <div class="tool-header" onclick="window.toggleTool(this)">
            <div><i class="fas fa-cog tool-icon"></i>${escapeHtml(toolName)}</div>
            <i class="fas fa-chevron-down tool-toggle-icon"></i>
        </div>
        <div class="tool-body">
            <pre style="margin:0;white-space:pre-wrap;font-size:12px;color:#666;">${escapeHtml(JSON.stringify(toolInput, null, 2))}</pre>
        </div>
    `;
    
    return card;
}

/**
 * 渲染工具结果
 */
function renderToolResult(part) {
    const card = document.createElement('div');
    card.className = 'tool-card expanded';
    
    const toolName = part.name || part.tool_name || 'result';
    const result = part.content || part.result || '';
    
    card.innerHTML = `
        <div class="tool-header" onclick="window.toggleTool(this)">
            <div><i class="fas fa-check-circle tool-icon" style="color:#28a745;"></i>${escapeHtml(toolName)} - 结果</div>
            <i class="fas fa-chevron-down tool-toggle-icon"></i>
        </div>
        <div class="tool-body">
            <div class="bash-cmd">${escapeHtml(String(result).substring(0, 1000))}${String(result).length > 1000 ? '...' : ''}</div>
        </div>
    `;
    
    return card;
}

/**
 * 发送消息
 */
export async function sendMessage() {
    const input = getDOM('chatInput');
    let content = input.value.trim();
    
    if (!AppState.currentSession) return;
    if (!content && AppState.pendingFiles.length === 0) return;
    
    const sessionId = AppState.currentSession.id;
    
    // 清空输入
    input.value = '';
    input.style.height = '44px';
    
    // 禁用发送按钮
    const sendBtn = getDOM('sendBtn');
    sendBtn.disabled = true;
    AppState.isStreaming = true;
    AppState.reasoningPartIds.clear();
    
    // 上传文件
    const { uploadPendingFiles } = await import('./upload.js');
    const uploadedFiles = await uploadPendingFiles();
    
    // 构建消息内容
    if (uploadedFiles.length > 0) {
        content += '\n\n[上传的文件]\n';
        uploadedFiles.forEach(f => {
            content += `- ${f.file_name}: ${f.absolute_path}\n`;
        });
    }
    
    // 初始化state
    ensureSessionState(sessionId);
    
    // 创建临时用户消息
    const tempUserMsgID = `temp_user_${Date.now()}`;
    AppState.messages[sessionId].push({
        id: tempUserMsgID,
        role: 'user',
        modelID: AppState.selectedModel,
        agent: AppState.selectedAgent,
        time: { created: Date.now() }
    });
    
    AppState.parts[sessionId][`part_${tempUserMsgID}`] = {
        id: `part_${tempUserMsgID}`,
        messageID: tempUserMsgID,
        type: 'text',
        text: content
    };
    
    // 更新session预览
    const session = AppState.sessions.find(s => (s.session_id || s.id) === sessionId);
    if (session) {
        session.last_message = content.substring(0, 30);
    }
    
    renderMessages();
    
    try {
        // 构建前缀
        const prefixData = {
            type: "web_message",
            user_qq: String(AppState.userQQ),
            user_name: AppState.userName || String(AppState.userQQ),
            session_id: sessionId,
            hint: `用户(${AppState.userName || AppState.userQQ}, QQ: ${AppState.userQQ})通过网页发送了一条消息。`
        };
        const prefix = `<Axeuh_bot>\n${JSON.stringify(prefixData, null, 0)}\n</Axeuh_bot>\n\n`;
        
        const requestBody = {
            parts: [{ type: 'text', text: prefix + content }]
        };
        
        if (AppState.selectedModel) {
            const modelParts = AppState.selectedModel.split('/');
            if (modelParts.length >= 2) {
                requestBody.model = {
                    modelID: modelParts.slice(1).join('/'),
                    providerID: modelParts[0]
                };
            } else {
                requestBody.model = {
                    modelID: AppState.selectedModel,
                    providerID: ''
                };
            }
        }
        if (AppState.selectedAgent) {
            requestBody.agent = AppState.selectedAgent;
        }
        
        await apiPost(`/api/opencode/sessions/${sessionId}/messages`, requestBody);
        
        // 更新后端会话时间
        apiPost('/api/session/switch', { user_id: AppState.userQQ, session_id: sessionId }).catch(e => {
            console.warn('[API] 更新会话时间失败:', e);
        });
    } catch (error) {
        console.error('发送消息失败:', error);
        sendBtn.disabled = false;
        AppState.isStreaming = false;
        
        // 添加错误消息
        ensureSessionState(sessionId);
        const errorMsgID = `error_msg_${Date.now()}`;
        AppState.messages[sessionId].push({
            id: errorMsgID,
            role: 'assistant',
            time: { created: Date.now() }
        });
        
        const errorPartID = `error_part_${Date.now()}`;
        AppState.parts[sessionId][errorPartID] = {
            id: errorPartID,
            messageID: errorMsgID,
            type: 'text',
            text: `发送失败: ${error.message}`
        };
        
        renderMessages();
    }
}

/**
 * 增量更新流式文本
 */
export function updateStreamingText(sessionId, partID, text) {
    const container = getDOM('messageContent');
    const partEl = container.querySelector(`[data-part-id="${partID}"]`);
    
    if (partEl) {
        if (partEl.classList.contains('ai-text')) {
            partEl.innerHTML = formatMarkdown(text);
            if (AppState.userAtBottom) {
                container.scrollTop = container.scrollHeight;
            }
            return true;
        }
        const thoughtText = partEl.querySelector('.thought-text');
        if (thoughtText) {
            thoughtText.textContent = text;
            if (AppState.userAtBottom) {
                container.scrollTop = container.scrollHeight;
            }
            return true;
        }
    }
    return false;
}

/**
 * 调度渲染（节流）
 */
export function scheduleRenderMessages() {
    scheduleRender(renderMessages, AppState);
}

/**
 * 切换工具卡片展开状态
 */
export function toggleTool(headerEl) {
    const card = headerEl.parentElement;
    card.classList.toggle('expanded');
}