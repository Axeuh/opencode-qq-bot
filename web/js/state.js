/**
 * 状态管理模块
 * 集中管理应用的所有状态
 */

export const AppState = {
    // 用户信息
    userQQ: null,
    userName: null,
    
    // 当前会话
    currentSession: null,
    
    // 选择配置
    selectedModel: null,
    selectedAgent: null,
    userConfig: {
        model: null,
        agent: null,
        provider: null
    },
    
    // 列表数据
    models: [],
    agents: [],
    sessions: [],
    
    // SSE连接
    eventSource: null,
    isStreaming: false,
    
    // 当前消息
    currentAIMessage: null,
    currentMessageID: null,
    reasoningPartIds: new Set(),
    
    // 消息和parts存储（按会话ID分组）
    messages: {},
    parts: {},
    
    // 会话状态
    sessionStatus: {},
    
    // 渲染优化
    userAtBottom: true,
    renderPending: false,
    lastRenderTime: 0,
    
    // 文件上传
    pendingFiles: [],
    
    // 发送设置（从localStorage恢复，默认开启）
    autoAbortBeforeSend: (typeof localStorage !== 'undefined' && localStorage.getItem('autoAbortBeforeSend') === 'false') ? false : true
};

/**
 * 确保会话状态存在
 * @param {string} sessionId - 会话ID
 */
export function ensureSessionState(sessionId) {
    if (!sessionId) return;
    
    if (!AppState.parts[sessionId]) {
        AppState.parts[sessionId] = {};
    }
    if (!AppState.messages[sessionId]) {
        AppState.messages[sessionId] = [];
    }
}

/**
 * 重置会话状态
 * @param {string} sessionId - 会话ID
 */
export function resetSessionState(sessionId) {
    if (!sessionId) return;
    
    AppState.parts[sessionId] = {};
    AppState.messages[sessionId] = [];
    AppState.sessionStatus[sessionId] = 'idle';
}

/**
 * 清理所有状态
 */
export function clearAllState() {
    AppState.userQQ = null;
    AppState.userName = null;
    AppState.currentSession = null;
    AppState.selectedModel = null;
    AppState.selectedAgent = null;
    AppState.userConfig = { model: null, agent: null, provider: null };
    AppState.models = [];
    AppState.agents = [];
    AppState.sessions = [];
    
    if (AppState.eventSource) {
        AppState.eventSource.close();
        AppState.eventSource = null;
    }
    
    AppState.isStreaming = false;
    AppState.currentAIMessage = null;
    AppState.currentMessageID = null;
    AppState.reasoningPartIds.clear();
    AppState.messages = {};
    AppState.parts = {};
    AppState.sessionStatus = {};
    AppState.pendingFiles = [];
}

// 导出渲染节流常量
export const RENDER_THROTTLE = 50;