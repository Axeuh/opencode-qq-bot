/**
 * SSE事件处理模块
 * 处理Server-Sent Events连接和事件分发
 */

import { AppState, ensureSessionState } from './state.js';
import { getAuthToken } from './api.js';
import { getDOM } from './utils.js';
import { renderMessages, scheduleRenderMessages, updateStreamingText } from './message.js';
import { renderSessions } from './session.js';

/**
 * 建立SSE连接
 */
export function connectSSE() {
    if (AppState.eventSource) {
        AppState.eventSource.close();
    }
    
    // 通过URL参数传递token
    const token = getAuthToken();
    const sseUrl = token ? `/api/opencode/events?token=${encodeURIComponent(token)}` : '/api/opencode/events';
    
    AppState.eventSource = new EventSource(sseUrl);
    
    AppState.eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleSSEEvent(data);
        } catch (e) {
            console.error('SSE 解析错误:', e);
        }
    };
    
    AppState.eventSource.onerror = (e) => {
        console.error('SSE 连接错误:', e);
        // 5秒后重连
        setTimeout(connectSSE, 5000);
    };
}

/**
 * 处理SSE事件
 * @param {object} rawData - 原始事件数据
 */
export function handleSSEEvent(rawData) {
    const type = rawData.payload?.type || rawData.type || rawData.event;
    const props = rawData.payload?.properties || rawData;
    
    // 检查是否是当前会话的事件
    let sessionId = props.sessionID || props.part?.sessionID || rawData.session_id;
    const currentSessionId = AppState.currentSession?.id;
    
    switch (type) {
        case 'server.connected':
            break;
            
        case 'server.heartbeat':
            break;
            
        case 'message.part.delta':
            handlePartDelta(props);
            break;
            
        case 'message.part.updated':
            handlePartUpdated(props);
            break;
            
        case 'message.updated':
            handleMessageUpdated(props);
            break;
            
        case 'session.status':
            handleSessionStatus(props);
            break;
            
        case 'session.created':
            break;
            
        case 'session.updated':
            handleSessionUpdated(props);
            break;
            
        case 'session.diff':
            handleSessionDiff(props);
            break;
            
        case 'message_start':
            break;
            
        case 'done':
        case 'message_end':
            AppState.isStreaming = false;
            getDOM('sendBtn').disabled = false;
            break;
            
        case 'error':
            AppState.isStreaming = false;
            getDOM('sendBtn').disabled = false;
            console.error('SSE错误:', props.message || rawData.message || rawData.error || '未知错误');
            break;
    }
}

/**
 * 处理消息part增量
 */
function handlePartDelta(props) {
    const deltaSessionId = props.sessionID;
    const partID = props.partID;
    const delta = props.delta || '';
    const field = props.field || 'text';
    const deltaMessageID = props.messageID;
    
    if (deltaSessionId && partID && field === 'text') {
        ensureSessionState(deltaSessionId);
        
        // 如果有messageID，确保对应的AI消息存在
        if (deltaMessageID) {
            const existingMsg = AppState.messages[deltaSessionId].find(m => m.id === deltaMessageID);
            if (!existingMsg) {
                AppState.messages[deltaSessionId].push({
                    id: deltaMessageID,
                    role: 'assistant',
                    sessionID: deltaSessionId,
                    time: { created: Date.now() }
                });
            }
            AppState.currentMessageID = deltaMessageID;
        }
        
        // 获取或创建part
        if (!AppState.parts[deltaSessionId][partID]) {
            AppState.parts[deltaSessionId][partID] = {
                text: '',
                id: partID,
                messageID: deltaMessageID
            };
        } else if (deltaMessageID && !AppState.parts[deltaSessionId][partID].messageID) {
            AppState.parts[deltaSessionId][partID].messageID = deltaMessageID;
        }
        
        // 追加文本
        const newText = (AppState.parts[deltaSessionId][partID].text || '') + delta;
        AppState.parts[deltaSessionId][partID].text = newText;
        
        // 如果是当前会话，尝试增量更新
        if (AppState.currentSession?.id === deltaSessionId) {
            const updated = updateStreamingText(deltaSessionId, partID, newText);
            if (!updated) {
                scheduleRenderMessages();
            }
        }
    }
}

/**
 * 处理消息part更新
 */
function handlePartUpdated(props) {
    const part = props.part || {};
    const partSessionId = part.sessionID;
    const partId = part.id;
    const partMessageID = part.messageID || props.messageID;
    
    if (partSessionId && partId) {
        ensureSessionState(partSessionId);
        
        if (partMessageID) {
            const existingMsg = AppState.messages[partSessionId].find(m => m.id === partMessageID);
            if (!existingMsg) {
                AppState.messages[partSessionId].push({
                    id: partMessageID,
                    role: 'assistant',
                    sessionID: partSessionId,
                    time: { created: Date.now() }
                });
            }
            AppState.currentMessageID = partMessageID;
        }
        
        AppState.parts[partSessionId][partId] = {
            ...AppState.parts[partSessionId][partId],
            ...part,
            messageID: partMessageID || AppState.parts[partSessionId][partId]?.messageID
        };
        
        if (AppState.currentSession?.id === partSessionId) {
            scheduleRenderMessages();
        }
    }
}

/**
 * 处理消息更新
 */
function handleMessageUpdated(props) {
    const info = props.info || {};
    const msgSessionId = info.sessionID || AppState.currentSession?.id;
    const msgId = info.id;
    const msgRole = info.role;
    
    if (msgSessionId && msgId) {
        ensureSessionState(msgSessionId);
        
        const existing = AppState.messages[msgSessionId].find(m => m.id === msgId);
        if (existing) {
            Object.assign(existing, info);
        } else {
            const tempMsg = AppState.messages[msgSessionId].find(
                m => m.id.toString().startsWith('temp_') && m.role === msgRole
            );
            if (tempMsg) {
                const idx = AppState.messages[msgSessionId].indexOf(tempMsg);
                const oldId = tempMsg.id;
                AppState.messages[msgSessionId][idx] = info;
                
                // 处理临时消息的parts
                if (msgRole === 'user' && AppState.parts[msgSessionId]) {
                    const tempPartPrefix = `part_${oldId}`;
                    Object.keys(AppState.parts[msgSessionId]).forEach(partId => {
                        if (partId.startsWith(tempPartPrefix) || AppState.parts[msgSessionId][partId].messageID === oldId) {
                            delete AppState.parts[msgSessionId][partId];
                        }
                    });
                }
                
                if (msgRole === 'assistant' && AppState.parts[msgSessionId]) {
                    const newPartsExist = Object.values(AppState.parts[msgSessionId])
                        .some(p => p.messageID === msgId && !p.id.toString().startsWith('part_temp_'));
                    
                    if (newPartsExist) {
                        Object.keys(AppState.parts[msgSessionId]).forEach(partId => {
                            if (AppState.parts[msgSessionId][partId].messageID === oldId) {
                                delete AppState.parts[msgSessionId][partId];
                            }
                        });
                    } else {
                        Object.values(AppState.parts[msgSessionId]).forEach(part => {
                            if (part.messageID === oldId) {
                                part.messageID = msgId;
                            }
                        });
                    }
                }
            } else {
                AppState.messages[msgSessionId].push(info);
            }
        }
        
        AppState.currentMessageID = msgId;
        
        // 更新session信息
        const session = AppState.sessions.find(s => (s.session_id || s.id) === msgSessionId);
        if (session) {
            const parts = AppState.parts[msgSessionId] || {};
            const lastMsgParts = Object.values(parts).filter(p => p.messageID === msgId && p.type === 'text');
            if (lastMsgParts.length > 0) {
                session.last_message = lastMsgParts.map(p => p.text || '').join('').substring(0, 30);
            }
            
            if (info.tokens) {
                const hasTokens = info.tokens.total > 0 ||
                    info.tokens.input > 0 ||
                    info.tokens.output > 0 ||
                    info.tokens.reasoning > 0 ||
                    (info.tokens.cache && (info.tokens.cache.read > 0 || info.tokens.cache.write > 0));
                
                if (hasTokens) {
                    session.tokens = info.tokens;
                    const totalTokens = info.tokens.total || (info.tokens.input || 0) + (info.tokens.output || 0) + (info.tokens.reasoning || 0);
                    getDOM('tokenCount').textContent = totalTokens.toLocaleString();
                }
            }
            
            session.updated_at = info.time?.updated || info.time?.created || Date.now();
            renderSessions();
        }
        
        if (AppState.currentSession?.id === msgSessionId) {
            scheduleRenderMessages();
        }
        
        // AI消息更新完成时，重置流式状态
        if (msgRole === 'assistant') {
            AppState.isStreaming = false;
            getDOM('sendBtn').disabled = false;
        }
    }
}

/**
 * 处理会话状态
 */
function handleSessionStatus(props) {
    const statusSessionId = props.sessionID;
    const statusValue = props.status || 'idle';
    if (statusSessionId) {
        AppState.sessionStatus[statusSessionId] = statusValue;
        if (AppState.currentSession?.id === statusSessionId) {
            renderMessages();
        }
    }
}

/**
 * 处理会话更新
 */
function handleSessionUpdated(props) {
    const updatedSessionId = props.sessionID || props.id;
    if (updatedSessionId) {
        const session = AppState.sessions.find(s => (s.session_id || s.id) === updatedSessionId);
        if (session && props.title) {
            session.title = props.title;
            session.updated_at = props.updated_at || Date.now();
            renderSessions();
        }
    }
}

/**
 * 处理会话差异更新
 */
function handleSessionDiff(props) {
    const diffSessionId = props.sessionID || props.id;
    if (diffSessionId && AppState.currentSession &&
        (AppState.currentSession.id === diffSessionId || AppState.currentSession.session_id === diffSessionId)) {
        if (props.directory !== undefined) {
            AppState.currentSession.directory = props.directory;
            // 更新路径显示
            const pathElement = getDOM('sessionPathHeader');
            if (pathElement) {
                pathElement.textContent = props.directory || '默认路径';
            }
        }
    }
}