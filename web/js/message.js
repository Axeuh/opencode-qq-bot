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
    
    // 保存当前工具卡片的折叠状态（true = 展开，false = 折叠）
    const toolExpandState = new Map();
    container.querySelectorAll('.tool-card[data-tool-id]').forEach(card => {
        toolExpandState.set(card.dataset.toolId, card.classList.contains('expanded'));
    });
    
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
    
    // 恢复工具卡片的折叠状态
    container.querySelectorAll('.tool-card[data-tool-id]').forEach(card => {
        const toolId = card.dataset.toolId;
        if (toolExpandState.has(toolId)) {
            // 用户之前操作过，恢复之前的状态
            const wasExpanded = toolExpandState.get(toolId);
            if (wasExpanded) {
                card.classList.add('expanded');
            } else {
                card.classList.remove('expanded');
            }
        }
        // 如果用户之前没有操作过，保持渲染器的默认状态
    });
    
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
        <div class="msg-user-footer">
            <div class="msg-user-actions">
                <button class="msg-action-btn msg-copy-btn" title="复制">
                    <i class="fas fa-copy"></i>
                </button>
                <button class="msg-action-btn msg-retract-btn" title="撤回">
                    <i class="fas fa-undo"></i>
                </button>
            </div>
            <div class="msg-user-info">${modelInfo} | ${agentInfo} | ${time}</div>
        </div>
    `;
    
    // 绑定复制按钮事件
    const copyBtn = wrap.querySelector('.msg-copy-btn');
    copyBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        copyMessageContent(content);
    });
    
    // 绑定撤回按钮事件
    const retractBtn = wrap.querySelector('.msg-retract-btn');
    retractBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        retractMessage(msg.id);
    });
    
    return wrap;
}

/**
 * 复制消息内容
 */
function copyMessageContent(content) {
    navigator.clipboard.writeText(content).then(() => {
        showSystemMessage('已复制到剪贴板');
    }).catch(err => {
        console.error('复制失败:', err);
        showSystemMessage('复制失败');
    });
}

/**
 * 撤回消息
 */
async function retractMessage(messageId) {
    if (!AppState.currentSession) return;
    
    const sessionId = AppState.currentSession.id;
    
    try {
        const { apiPost } = await import('./api.js');
        const result = await apiPost(`/api/opencode/sessions/${sessionId}/revert`, {
            messageID: messageId
        });
        
        if (result === true || result.success) {
            showSystemMessage('已撤回消息');
            // 刷新消息列表
            setTimeout(() => loadMessages(sessionId), 500);
        } else {
            showSystemMessage('撤回失败: ' + (result.error || '未知错误'));
        }
    } catch (e) {
        console.error('撤回消息失败:', e);
        showSystemMessage('撤回失败: ' + e.message);
    }
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

// ============================================
// 工具渲染器映射表 - 可扩展架构
// ============================================

/**
 * 工具图标配置
 */
const TOOL_ICONS = {
    bash: { icon: 'fa-terminal', color: '#333' },
    read: { icon: 'fa-file-code', color: '#3b82f6' },
    write: { icon: 'fa-save', color: '#10b981' },
    edit: { icon: 'fa-edit', color: '#f59e0b' },
    glob: { icon: 'fa-folder-open', color: '#8b5cf6' },
    grep: { icon: 'fa-search', color: '#06b6d4' },
    lsp_diagnostics: { icon: 'fa-bug', color: '#ef4444' },
    lsp_goto_definition: { icon: 'fa-arrow-right', color: '#6366f1' },
    lsp_find_references: { icon: 'fa-link', color: '#8b5cf6' },
    lsp_symbols: { icon: 'fa-code', color: '#14b8a6' },
    ast_grep_search: { icon: 'fa-search-plus', color: '#f97316' },
    ast_grep_replace: { icon: 'fa-exchange-alt', color: '#ec4899' },
    webfetch: { icon: 'fa-globe', color: '#0ea5e9' },
    skill: { icon: 'fa-puzzle-piece', color: '#a855f7' },
    skill_mcp: { icon: 'fa-plug', color: '#7c3aed' },
    task: { icon: 'fa-tasks', color: '#f59e0b' },
    look_at: { icon: 'fa-eye', color: '#06b6d4' },
    pty_spawn: { icon: 'fa-terminal', color: '#64748b' },
    default: { icon: 'fa-cog', color: '#6b7280' }
};

/**
 * 渲染 Diff 视图（使用 CSS 样式）
 * @param {string} oldText - 旧文本
 * @param {string} newText - 新文本
 * @param {number} maxLines - 最大显示行数
 * @returns {string} HTML 字符串
 */
function renderDiffView(oldText, newText, maxLines = 50) {
    const oldLines = oldText.split('\n');
    const newLines = newText.split('\n');
    const result = [];
    
    // 简单的行对行比较
    const maxLen = Math.max(oldLines.length, newLines.length);
    let lineNum = 1;
    let displayedLines = 0;
    
    for (let i = 0; i < maxLen && displayedLines < maxLines; i++) {
        const oldLine = oldLines[i];
        const newLine = newLines[i];
        
        // 删除行（红色）
        if (oldLine !== undefined && (newLine === undefined || oldLine !== newLine)) {
            result.push(`<div class="diff-line diff-del"><span class="diff-num">${lineNum}</span><span class="diff-code">- ${escapeHtml(oldLine)}</span></div>`);
            displayedLines++;
        }
        
        // 添加行（绿色）
        if (newLine !== undefined && (oldLine === undefined || oldLine !== newLine)) {
            result.push(`<div class="diff-line diff-add"><span class="diff-num">${lineNum}</span><span class="diff-code">+ ${escapeHtml(newLine)}</span></div>`);
            lineNum++;
            displayedLines++;
        }
        
        // 相同行
        if (oldLine === newLine && oldLine !== undefined) {
            result.push(`<div class="diff-line"><span class="diff-num">${lineNum}</span><span class="diff-code">  ${escapeHtml(oldLine)}</span></div>`);
            lineNum++;
            displayedLines++;
        }
    }
    
    if (maxLen > maxLines) {
        result.push(`<div style="padding:8px;color:#888;text-align:center;">... 省略 ${maxLen - maxLines} 行</div>`);
    }
    
    return `<div class="diff-container">${result.join('')}</div>`;
}

/**
 * 获取工具图标配置
 */
function getToolIcon(toolName) {
    return TOOL_ICONS[toolName] || TOOL_ICONS.default;
}

/**
 * 创建工具卡片基础结构
 */
function createToolCardBase(toolName, options = {}) {
    const card = document.createElement('div');
    card.className = 'tool-card';
    if (options.expanded) card.classList.add('expanded');
    if (options.toolId) card.dataset.toolId = options.toolId;
    
    const icon = getToolIcon(toolName);
    const title = options.title || toolName;
    const subtitle = options.subtitle || '';
    
    card.innerHTML = `
        <div class="tool-header" onclick="window.toggleTool(this)" ${options.titleAttr ? `title="${escapeHtml(options.titleAttr)}"` : ''}>
            <div><i class="fas ${icon.icon} tool-icon" style="color:${icon.color};"></i>${escapeHtml(title)}${subtitle ? ` · ${escapeHtml(subtitle)}` : ''}</div>
            <i class="fas fa-chevron-down tool-toggle-icon"></i>
        </div>
        <div class="tool-body"></div>
    `;
    
    return card;
}

/**
 * 渲染 Bash 工具
 */
function renderBashTool(part, toolId) {
    const state = part.state || {};
    const input = state.input || {};
    const output = state.output || '';
    const command = input.command || input.cmd || '';
    const description = input.description || '';
    const exitCode = state.exitCode !== undefined ? state.exitCode : '0';
    const isSuccess = exitCode === 0 || exitCode === '0';
    
    const displayTitle = description || command;
    const shortTitle = displayTitle.length > 50 ? displayTitle.substring(0, 47) + '...' : displayTitle;
    const cleanOutput = String(output).replace(/Exit Code:\s*\d+.*$/s, '').trim();
    const truncatedOutput = cleanOutput.substring(0, 2000);
    
    const card = createToolCardBase('bash', {
        expanded: true,
        title: 'bash',
        subtitle: shortTitle,
        titleAttr: displayTitle,
        toolId: toolId
    });
    
    const body = card.querySelector('.tool-body');
    body.innerHTML = `
        <div class="bash-cmd">$ ${escapeHtml(command)}
${escapeHtml(truncatedOutput)}${cleanOutput.length > 2000 ? '\n...(输出过长已截断)' : ''}</div>
        <div class="bash-status" style="color: ${isSuccess ? '#28a745' : '#dc3545'};">
            <i class="fas ${isSuccess ? 'fa-check-circle' : 'fa-times-circle'}"></i> 
            Exit Code: ${exitCode} ${isSuccess ? '(Success)' : '(Failed)'}
        </div>
    `;
    
    return card;
}

/**
 * 渲染 Read 工具
 */
function renderReadTool(part, toolId) {
    const state = part.state || {};
    const input = state.input || {};
    const output = state.output || '';
    const filePath = input.filePath || input.file_path || input.path || '';
    
    const card = createToolCardBase('read', {
        expanded: true,
        title: 'read',
        subtitle: filePath.split('/').pop() || 'file',
        toolId: toolId
    });
    
    const body = card.querySelector('.tool-body');
    const lines = String(output).split('\n').length;
    const truncatedOutput = String(output).substring(0, 3000);
    
    body.innerHTML = `
        <div class="tool-info" style="font-size:12px;color:#666;margin-bottom:8px;">
            <i class="fas fa-file"></i> ${escapeHtml(filePath)} (${lines} lines)
        </div>
        <pre class="code-preview" style="margin:0;white-space:pre-wrap;font-size:12px;font-family:monospace;background:#f8fafc;padding:8px;border-radius:6px;max-height:300px;overflow-y:auto;">${escapeHtml(truncatedOutput)}${String(output).length > 3000 ? '\n...(内容过长已截断)' : ''}</pre>
    `;
    
    return card;
}

/**
 * 渲染 Write 工具
 */
function renderWriteTool(part, toolId) {
    const state = part.state || {};
    const input = state.input || {};
    const output = state.output || '';
    const filePath = input.filePath || input.file_path || input.path || '';
    
    const card = createToolCardBase('write', {
        title: 'write',
        subtitle: filePath.split('/').pop() || 'file',
        toolId: toolId
    });
    
    const body = card.querySelector('.tool-body');
    const content = input.content || '';
    const lines = content.split('\n').length;
    
    body.innerHTML = `
        <div class="tool-info" style="font-size:12px;color:#666;">
            <i class="fas fa-save"></i> ${escapeHtml(filePath)} (${lines} lines written)
        </div>
        ${output ? `<div class="bash-cmd" style="margin-top:8px;font-size:12px;">${escapeHtml(String(output).substring(0, 500))}</div>` : ''}
    `;
    
    return card;
}

/**
 * 渲染 Edit 工具
 */
function renderEditTool(part, toolId) {
    const state = part.state || {};
    const input = state.input || {};
    const output = state.output || '';
    const filePath = input.filePath || input.file_path || input.path || '';
    
    const card = createToolCardBase('edit', {
        expanded: true,
        title: 'edit',
        subtitle: filePath.split('/').pop() || 'file',
        toolId: toolId
    });
    
    const body = card.querySelector('.tool-body');
    const oldString = input.oldString || input.old_string || '';
    const newString = input.newString || input.new_string || '';
    
    // 使用 renderDiffView 渲染 diff 视图
    const diffHtml = renderDiffView(oldString, newString, 30);
    
    body.innerHTML = `
        <div class="tool-info" style="font-size:12px;color:#666;margin-bottom:8px;">
            <i class="fas fa-file"></i> ${escapeHtml(filePath)}
        </div>
        ${diffHtml}
        ${output ? `<div class="bash-cmd" style="margin-top:8px;font-size:12px;">${escapeHtml(String(output).substring(0, 500))}</div>` : ''}
    `;
    
    return card;
}

/**
 * 渲染 Glob 工具
 */
function renderGlobTool(part, toolId) {
    const state = part.state || {};
    const input = state.input || {};
    const output = state.output || '';
    const pattern = input.pattern || '*';
    
    const card = createToolCardBase('glob', {
        title: 'glob',
        subtitle: pattern,
        toolId: toolId
    });
    
    const body = card.querySelector('.tool-body');
    const files = Array.isArray(output) ? output : (typeof output === 'string' ? output.split('\n').filter(f => f.trim()) : []);
    const fileCount = files.length;
    const displayFiles = files.slice(0, 20);
    
    body.innerHTML = `
        <div class="tool-info" style="font-size:12px;color:#666;margin-bottom:8px;">
            <i class="fas fa-folder-open"></i> Pattern: <code>${escapeHtml(pattern)}</code> (${fileCount} files)
        </div>
        <div class="file-list" style="font-size:12px;font-family:monospace;max-height:200px;overflow-y:auto;">
            ${displayFiles.map(f => `<div style="padding:2px 0;"><i class="fas fa-file" style="color:#888;margin-right:4px;"></i>${escapeHtml(f.split('/').pop())}</div>`).join('')}
            ${fileCount > 20 ? `<div style="color:#888;padding:4px 0;">... and ${fileCount - 20} more files</div>` : ''}
        </div>
    `;
    
    return card;
}

/**
 * 渲染 Grep 工具
 */
function renderGrepTool(part, toolId) {
    const state = part.state || {};
    const input = state.input || {};
    const output = state.output || '';
    const pattern = input.pattern || '';
    const path = input.path || '';
    
    const card = createToolCardBase('grep', {
        expanded: true,
        title: 'grep',
        subtitle: pattern.substring(0, 30),
        toolId: toolId
    });
    
    const body = card.querySelector('.tool-body');
    const lines = String(output).split('\n').filter(l => l.trim());
    const matchCount = lines.length;
    const displayLines = lines.slice(0, 30);
    
    body.innerHTML = `
        <div class="tool-info" style="font-size:12px;color:#666;margin-bottom:8px;">
            <i class="fas fa-search"></i> Pattern: <code>${escapeHtml(pattern)}</code> in ${escapeHtml(path || '.')} (${matchCount} matches)
        </div>
        <pre class="grep-output" style="margin:0;white-space:pre-wrap;font-size:11px;font-family:monospace;background:#f8fafc;padding:8px;border-radius:6px;max-height:250px;overflow-y:auto;">${escapeHtml(displayLines.join('\n'))}${matchCount > 30 ? `\n... and ${matchCount - 30} more matches` : ''}</pre>
    `;
    
    return card;
}

/**
 * 渲染 WebFetch 工具
 */
function renderWebfetchTool(part, toolId) {
    const state = part.state || {};
    const input = state.input || {};
    const output = state.output || '';
    const url = input.url || '';
    
    const card = createToolCardBase('webfetch', {
        title: 'webfetch',
        subtitle: url.substring(0, 40),
        toolId: toolId
    });
    
    const body = card.querySelector('.tool-body');
    const truncatedOutput = String(output).substring(0, 2000);
    
    body.innerHTML = `
        <div class="tool-info" style="font-size:12px;color:#666;margin-bottom:8px;">
            <i class="fas fa-globe"></i> <a href="${escapeHtml(url)}" target="_blank" style="color:#3b82f6;">${escapeHtml(url)}</a>
        </div>
        <pre style="margin:0;white-space:pre-wrap;font-size:11px;font-family:monospace;background:#f8fafc;padding:8px;border-radius:6px;max-height:200px;overflow-y:auto;">${escapeHtml(truncatedOutput)}${String(output).length > 2000 ? '...' : ''}</pre>
    `;
    
    return card;
}

/**
 * 渲染通用工具（后备）
 */
function renderGenericTool(part, toolId) {
    const toolName = part.tool || 'tool';
    const state = part.state || {};
    const input = state.input || {};
    const output = state.output || '';
    
    const card = createToolCardBase(toolName, { title: toolName, toolId: toolId });
    const body = card.querySelector('.tool-body');
    
    body.innerHTML = `
        <pre style="margin:0;white-space:pre-wrap;font-size:12px;color:#666;background:#f8fafc;padding:8px;border-radius:6px;max-height:150px;overflow-y:auto;">${escapeHtml(JSON.stringify(input, null, 2))}</pre>
        ${output ? `<div class="bash-cmd" style="margin-top:8px;max-height:200px;overflow-y:auto;">${escapeHtml(String(output).substring(0, 2000))}${String(output).length > 2000 ? '...' : ''}</div>` : ''}
    `;
    
    return card;
}

/**
 * 工具渲染器映射表
 * 新增工具只需在此添加映射即可
 */
const TOOL_RENDERERS = {
    bash: renderBashTool,
    read: renderReadTool,
    write: renderWriteTool,
    edit: renderEditTool,
    glob: renderGlobTool,
    grep: renderGrepTool,
    webfetch: renderWebfetchTool,
    // 添加更多工具渲染器...
};

/**
 * 注册新的工具渲染器
 * @param {string} toolName - 工具名称
 * @param {function} renderer - 渲染函数
 */
export function registerToolRenderer(toolName, renderer) {
    TOOL_RENDERERS[toolName] = renderer;
}

/**
 * 渲染工具调用part（主入口）
 */
function renderToolPart(part) {
    const toolName = part.tool || 'tool';
    const toolId = part.id || `tool_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const renderer = TOOL_RENDERERS[toolName];
    
    if (renderer) {
        return renderer(part, toolId);
    }
    
    // 尝试模糊匹配
    for (const [name, rend] of Object.entries(TOOL_RENDERERS)) {
        if (toolName.includes(name) || name.includes(toolName)) {
            return rend(part, toolId);
        }
    }
    
    return renderGenericTool(part, toolId);
}

/**
 * 渲染工具卡片
 */
function renderToolCard(part) {
    const toolName = part.name || part.tool_name || 'tool';
    const toolInput = part.input || part.arguments || {};
    
    // 特殊处理：question工具
    if (toolName === 'question') {
        return renderQuestionCard(part);
    }
    
    const card = document.createElement('div');
    card.className = 'tool-card';
    
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
 * 渲染Question工具卡片
 */
function renderQuestionCard(part) {
    const input = part.input || part.arguments || {};
    const questions = input.questions || [];
    const partId = part.id || 'question_' + Date.now();
    
    const card = document.createElement('div');
    card.className = 'question-card';
    card.dataset.partId = partId;
    
    const questionsHtml = questions.map((q, qIndex) => {
        const header = q.header || '选择';
        const questionText = q.question || '';
        const options = q.options || [];
        const multiple = q.multiple || false;
        
        const optionsHtml = options.map((opt, optIndex) => {
            const label = opt.label || '';
            const description = opt.description || '';
            const inputType = multiple ? 'checkbox' : 'radio';
            const inputName = partId + '_q' + qIndex;
            
            return `<label class="question-option" data-question-index="${qIndex}" data-option-index="${optIndex}">
                <input type="${inputType}" name="${inputName}" value="${escapeHtml(label)}" class="question-input">
                <div class="option-content">
                    <span class="option-label">${escapeHtml(label)}</span>
                    ${description ? `<span class="option-desc">${escapeHtml(description)}</span>` : ''}
                </div>
            </label>`;
        }).join('');
        
        return `<div class="question-block" data-question-index="${qIndex}">
            <div class="question-header">${escapeHtml(header)}</div>
            ${questionText ? `<div class="question-text">${escapeHtml(questionText)}</div>` : ''}
            <div class="question-options">${optionsHtml}</div>
        </div>`;
    }).join('');
    
    card.innerHTML = `
        <div class="question-card-header">
            <i class="fas fa-question-circle question-icon"></i>
            <span>请选择</span>
        </div>
        <div class="question-card-body">
            ${questionsHtml}
            <button class="question-submit-btn" onclick="window.handleQuestionAnswer('${partId}')">
                <i class="fas fa-paper-plane"></i> 提交回答
            </button>
        </div>
    `;
    
    return card;
}

/**
 * 处理用户回答问题
 */
window.handleQuestionAnswer = function(partId) {
    const card = document.querySelector(`.question-card[data-part-id="${partId}"]`);
    if (!card) return;
    
    // 收集所有问题的答案
    const answers = [];
    const questionBlocks = card.querySelectorAll('.question-block');
    
    questionBlocks.forEach((block, qIndex) => {
        const selectedOptions = block.querySelectorAll('.question-input:checked');
        const selectedLabels = Array.from(selectedOptions).map(input => input.value);
        
        if (selectedLabels.length > 0) {
            answers.push({ questionIndex: qIndex, selected: selectedLabels });
        }
    });
    
    if (answers.length === 0) return;
    
    // 构建回复消息
    let replyContent = '';
    answers.forEach(answer => {
        if (answer.selected.length === 1) {
            replyContent += answer.selected[0];
        } else {
            replyContent += answer.selected.join(', ');
        }
    });
    
    // 禁用按钮，显示已提交状态
    const submitBtn = card.querySelector('.question-submit-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-check"></i> 已提交';
        submitBtn.classList.add('submitted');
    }
    
    // 禁用所有选项
    card.querySelectorAll('.question-input').forEach(input => { input.disabled = true; });
    
    // 发送消息
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.value = replyContent;
        const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
        chatInput.dispatchEvent(event);
    }
};

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
 * 处理命令
 * @param {string} content - 命令内容
 * @returns {boolean} 是否已处理（true表示不需要发送消息）
 */
function handleCommand(content) {
    const trimmed = content.trim();
    
    // 检查是否是命令格式
    if (!trimmed.startsWith('/')) {
        return false;
    }
    
    // 解析命令和参数
    const parts = trimmed.slice(1).split(/\s+/);
    const commandName = parts[0].toLowerCase();
    const args = parts.slice(1).join(' ');
    
    // 特殊命令：前端直接处理
    if (commandName === 'stop') {
        stopSession();
        return true;
    }
    
    if (commandName === 'compact') {
        compactSession();
        return true;
    }
    
    if (commandName === 'undo') {
        undoSession();
        return true;
    }
    
    if (commandName === 'redo') {
        redoSession();
        return true;
    }
    
    // 其他命令：发送到后端执行
    executeBackendCommand(commandName, args);
    return true;
}

/**
 * 执行后端命令
 */
async function executeBackendCommand(command, args = '') {
    if (!AppState.currentSession) return;
    
    const sessionId = AppState.currentSession.id;
    
    try {
        const { executeCommand } = await import('./api.js');
        const result = await executeCommand(sessionId, command, args ? { input: args } : {});
        
        if (result.info) {
            // 命令执行成功，结果会通过SSE推送
            showSystemMessage(`命令 /${command} 执行成功`);
        } else if (result.error) {
            showSystemMessage(`命令失败: ${result.error}`);
        }
    } catch (e) {
        console.error('执行命令失败:', e);
        showSystemMessage(`命令失败: ${e.message}`);
    }
}

/**
 * 压缩对话历史
 */
async function compactSession() {
    if (!AppState.currentSession) return;
    
    const sessionId = AppState.currentSession.id;
    
    try {
        const { apiPost } = await import('./api.js');
        
        // 获取当前模型信息
        const modelParts = AppState.selectedModel ? AppState.selectedModel.split('/') : [];
        const body = {};
        
        if (modelParts.length >= 2) {
            body.providerID = modelParts[0];
            body.modelID = modelParts.slice(1).join('/');
        } else if (AppState.selectedModel) {
            body.modelID = AppState.selectedModel;
            body.providerID = '';
        }
        
        const result = await apiPost(`/api/opencode/sessions/${sessionId}/summarize`, body);
        
        if (result === true || result.success || result.status === 'ok') {
            showSystemMessage('对话历史已压缩');
        } else {
            showSystemMessage('压缩失败: ' + (result.error || '未知错误'));
        }
    } catch (e) {
        console.error('压缩对话失败:', e);
        showSystemMessage('压缩失败: ' + e.message);
    }
}

/**
 * 撤销上一条消息 (undo)
 */
async function undoSession() {
    if (!AppState.currentSession) return;
    
    const sessionId = AppState.currentSession.id;
    const messages = AppState.messages[sessionId] || [];
    
    // 找到最后一条非临时消息
    let lastMessage = null;
    for (let i = messages.length - 1; i >= 0; i--) {
        const msg = messages[i];
        if (msg.id && !msg.id.startsWith('temp_')) {
            lastMessage = msg;
            break;
        }
    }
    
    if (!lastMessage) {
        showSystemMessage('没有可撤销的消息');
        return;
    }
    
    try {
        const { apiPost } = await import('./api.js');
        
        const result = await apiPost(`/api/opencode/sessions/${sessionId}/revert`, {
            messageID: lastMessage.id
        });
        
        if (result === true || result.success) {
            showSystemMessage('已撤销上一条消息');
            // 刷新消息列表
            setTimeout(() => loadMessages(sessionId), 500);
        } else {
            showSystemMessage('撤销失败: ' + (result.error || '未知错误'));
        }
    } catch (e) {
        console.error('撤销消息失败:', e);
        showSystemMessage('撤销失败: ' + e.message);
    }
}

/**
 * 重做撤销的消息 (redo)
 */
async function redoSession() {
    if (!AppState.currentSession) return;
    
    const sessionId = AppState.currentSession.id;
    
    try {
        const { apiPost } = await import('./api.js');
        
        const result = await apiPost(`/api/opencode/sessions/${sessionId}/unrevert`, {});
        
        if (result === true || result.success) {
            showSystemMessage('已恢复撤销的消息');
            // 刷新消息列表
            setTimeout(() => loadMessages(sessionId), 500);
        } else {
            showSystemMessage('重做失败: ' + (result.error || '没有可恢复的消息'));
        }
    } catch (e) {
        console.error('重做消息失败:', e);
        showSystemMessage('重做失败: ' + e.message);
    }
}

/**
 * 显示系统提示消息
 */
function showSystemMessage(text) {
    const toast = document.createElement('div');
    toast.className = 'system-toast';
    toast.textContent = text;
    toast.style.cssText = `
        position: fixed;
        top: 80px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(0,0,0,0.8);
        color: #fff;
        padding: 10px 20px;
        border-radius: 8px;
        z-index: 1000;
        animation: fadeInOut 2s ease;
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.remove(), 2000);
}

/**
 * 发送消息（异步，不等待结果）
 */
export function sendMessage() {
    const input = getDOM('chatInput');
    let content = input.value.trim();
    
    if (!AppState.currentSession) return;
    if (!content && AppState.pendingFiles.length === 0) return;
    
    // 清空输入
    input.value = '';
    input.style.height = '44px';
    
    // 隐藏命令菜单
    const commandMenu = getDOM('commandMenu');
    if (commandMenu) commandMenu.style.display = 'none';
    
    // 处理命令
    if (handleCommand(content)) {
        return;
    }
    
    const sessionId = AppState.currentSession.id;
    
    // 异步发送，不等待结果
    (async () => {
        try {
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
            
            // 更新后端会话时间（不等待结果）
            apiPost('/api/session/switch', { user_id: AppState.userQQ, session_id: sessionId }).catch(() => {});
            
        } catch (error) {
            console.error('发送消息失败:', error);
        }
    })();
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

/**
 * 中止当前会话
 */
export async function stopSession() {
    if (!AppState.currentSession) return;
    
    const sessionId = AppState.currentSession.id;
    const { abortSession } = await import('./api.js');
    
    try {
        const result = await abortSession(sessionId);
        if (result.success || result === true) {
            AppState.isStreaming = false;
            updateSendStopButtons();
            console.log('会话已中止');
        }
    } catch (e) {
        console.error('中止会话失败:', e);
    }
}

/**
 * 更新发送/停止按钮状态
 */
export function updateSendStopButtons() {
    const sendBtn = getDOM('sendBtn');
    const stopBtn = getDOM('stopBtn');
    
    if (AppState.isStreaming) {
        if (sendBtn) sendBtn.style.display = 'none';
        if (stopBtn) stopBtn.style.display = 'flex';
    } else {
        if (sendBtn) sendBtn.style.display = 'flex';
        if (stopBtn) stopBtn.style.display = 'none';
    }
}

// 命令列表缓存
let commandsCache = null;

// 前端特殊命令（不发送到后端）
const SPECIAL_COMMANDS = [
    { name: 'stop', description: '停止当前会话的生成' },
    { name: 'compact', description: '压缩对话历史，减少token使用' },
    { name: 'undo', description: '撤销上一条消息' },
    { name: 'redo', description: '恢复撤销的消息' }
];

/**
 * 获取命令列表
 */
async function getCommandsList() {
    if (commandsCache) return commandsCache;
    
    try {
        const { getCommands } = await import('./api.js');
        const backendCommands = await getCommands() || [];
        
        // 合并后端命令和前端特殊命令
        commandsCache = [...SPECIAL_COMMANDS, ...backendCommands];
        return commandsCache;
    } catch (e) {
        console.error('获取命令列表失败:', e);
        // 返回特殊命令
        return SPECIAL_COMMANDS;
    }
}

/**
 * 显示命令菜单
 */
export async function showCommandMenu(filter = '') {
    const commandMenu = getDOM('commandMenu');
    const commandMenuList = getDOM('commandMenuList');
    
    if (!commandMenu || !commandMenuList) return;
    
    const commands = await getCommandsList();
    
    // 过滤命令
    const filteredCommands = commands.filter(cmd => {
        const name = cmd.name || cmd;
        return name.toLowerCase().includes(filter.toLowerCase());
    });
    
    if (filteredCommands.length === 0) {
        commandMenu.style.display = 'none';
        return;
    }
    
    // 渲染命令列表
    commandMenuList.innerHTML = filteredCommands.map((cmd, index) => {
        const name = cmd.name || cmd;
        const desc = cmd.description || '';
        return `<div class="command-item" data-command="/${name}" data-index="${index}">
            <span class="command-name">/${name}</span>
            ${desc ? `<span class="command-desc">${desc}</span>` : ''}
        </div>`;
    }).join('');
    
    // 绑定点击事件
    commandMenuList.querySelectorAll('.command-item').forEach(item => {
        item.addEventListener('click', () => {
            const cmd = item.dataset.command;
            const input = getDOM('chatInput');
            input.value = cmd + ' ';
            input.focus();
            commandMenu.style.display = 'none';
        });
    });
    
    commandMenu.style.display = 'block';
}

/**
 * 隐藏命令菜单
 */
export function hideCommandMenu() {
    const commandMenu = getDOM('commandMenu');
    if (commandMenu) commandMenu.style.display = 'none';
}