/**
 * 配置选择模块
 * 处理模型和智能体的选择
 */

import { AppState } from './state.js';
import { apiGet, apiPost } from './api.js';
import { getDOM } from './utils.js';

/**
 * 加载模型列表
 */
export async function loadModels() {
    try {
        const result = await apiGet('/api/models');
        if (result && result.success && Array.isArray(result.models)) {
            AppState.models = result.models.map(id => {
                const parts = id.split('/');
                const modelId = parts.slice(1).join('/');
                const provider = parts[0];
                return {
                    id: id,
                    name: modelId || id,
                    provider: provider
                };
            });
        } else {
            AppState.models = [];
        }
        renderModelSelect();
    } catch (error) {
        console.error('加载模型列表失败:', error);
        AppState.models = [];
        renderModelSelect();
    }
}

/**
 * 加载智能体列表
 */
export async function loadAgents() {
    try {
        const result = await apiGet('/api/agents');
        if (result && result.success && Array.isArray(result.agents)) {
            AppState.agents = result.agents.map(agent => {
                if (typeof agent === 'object' && agent !== null) {
                    return {
                        id: agent.id || agent.name || agent,
                        name: agent.name || agent.id || agent
                    };
                } else {
                    return {
                        id: agent,
                        name: agent
                    };
                }
            });
        } else {
            AppState.agents = [];
        }
        renderAgentSelect();
    } catch (error) {
        console.error('加载智能体列表失败:', error);
        AppState.agents = [];
        renderAgentSelect();
    }
}

/**
 * 渲染模型选择器
 */
export function renderModelSelect() {
    const container = getDOM('modelItems');
    const selected = document.querySelector('#modelSelect .select-selected');
    const selectedText = selected.querySelector('.select-selected-text');
    
    const currentModelId = AppState.userConfig.model || AppState.selectedModel;
    
    container.innerHTML = '';
    
    if (AppState.models.length === 0) {
        container.innerHTML = '<div style="padding:8px 12px;color:#999;">暂无可用模型</div>';
        selectedText.textContent = '无模型';
        selected.dataset.value = '';
        return;
    }
    
    AppState.models.forEach(model => {
        const item = document.createElement('div');
        item.textContent = model.name || model.id || model;
        item.dataset.value = model.id || model;
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            selectedText.textContent = item.textContent;
            selected.dataset.value = item.dataset.value;
            AppState.selectedModel = item.dataset.value;
            container.classList.remove('select-show');
            saveModelSelection(item.dataset.value);
        });
        container.appendChild(item);
    });
    
    // 匹配用户配置的模型
    if (currentModelId) {
        const model = AppState.models.find(m =>
            m.id === currentModelId ||
            m.id.toLowerCase() === currentModelId.toLowerCase() ||
            m.id.endsWith('/' + currentModelId) ||
            m.id.toLowerCase().endsWith('/' + currentModelId.toLowerCase()) ||
            m.name === currentModelId ||
            m.name.toLowerCase() === currentModelId.toLowerCase()
        );
        if (model) {
            selectedText.textContent = model.name || model.id;
            selected.dataset.value = model.id;
            AppState.selectedModel = model.id;
            return;
        }
    }
    
    selectedText.textContent = '选择模型';
    selected.dataset.value = '';
    AppState.selectedModel = null;
}

/**
 * 渲染智能体选择器
 */
export function renderAgentSelect() {
    const container = getDOM('agentItems');
    const selected = document.querySelector('#agentSelect .select-selected');
    const selectedText = selected.querySelector('.select-selected-text');
    
    const currentAgentId = AppState.userConfig.agent || AppState.selectedAgent;
    
    container.innerHTML = '';
    
    if (AppState.agents.length === 0) {
        container.innerHTML = '<div style="padding:8px 12px;color:#999;">暂无可用智能体</div>';
        selectedText.textContent = '无智能体';
        selected.dataset.value = '';
        return;
    }
    
    AppState.agents.forEach(agent => {
        const item = document.createElement('div');
        item.textContent = agent.name || agent.id;
        item.dataset.value = agent.id;
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            selectedText.textContent = item.textContent;
            selected.dataset.value = item.dataset.value;
            AppState.selectedAgent = item.dataset.value;
            container.classList.remove('select-show');
            saveAgentSelection(item.dataset.value);
        });
        container.appendChild(item);
    });
    
    // 匹配用户配置的智能体
    if (currentAgentId) {
        const agent = AppState.agents.find(a =>
            a.id === currentAgentId ||
            a.id.toLowerCase() === currentAgentId.toLowerCase()
        );
        
        if (agent) {
            selectedText.textContent = agent.name || agent.id;
            selected.dataset.value = agent.id;
            AppState.selectedAgent = agent.id;
            return;
        }
    }
    
    selectedText.textContent = '选择智能体';
    selected.dataset.value = '';
    AppState.selectedAgent = null;
}

/**
 * 保存模型选择
 * @param {string} modelId - 模型ID
 */
export async function saveModelSelection(modelId) {
    if (!AppState.userQQ) return;
    try {
        await apiPost('/api/model/set', { user_id: AppState.userQQ, model: modelId });
    } catch (error) {
        console.error('保存模型选择失败:', error);
    }
}

/**
 * 保存智能体选择
 * @param {string} agentId - 智能体ID
 */
export async function saveAgentSelection(agentId) {
    if (!AppState.userQQ) return;
    try {
        await apiPost('/api/agents/set', { user_id: AppState.userQQ, agent: agentId });
    } catch (error) {
        console.error('保存智能体选择失败:', error);
    }
}

/**
 * 更新用户选择显示
 */
export function updateUserSelections() {
    // 更新模型选择
    const savedModel = AppState.userConfig.model;
    if (savedModel && AppState.models.length > 0) {
        const model = AppState.models.find(m =>
            m.id === savedModel ||
            m.id.toLowerCase() === savedModel.toLowerCase() ||
            m.id.endsWith('/' + savedModel) ||
            m.id.toLowerCase().endsWith('/' + savedModel.toLowerCase()) ||
            m.name === savedModel ||
            m.name.toLowerCase() === savedModel.toLowerCase()
        );
        if (model) {
            const selected = document.querySelector('#modelSelect .select-selected');
            const selectedText = selected.querySelector('.select-selected-text');
            selectedText.textContent = model.name || model.id;
            selected.dataset.value = model.id;
            AppState.selectedModel = model.id;
        }
    }
    
    // 更新智能体选择
    const savedAgent = AppState.userConfig.agent;
    if (savedAgent && AppState.agents.length > 0) {
        const agent = AppState.agents.find(a =>
            a.id === savedAgent ||
            a.id.toLowerCase() === savedAgent.toLowerCase() ||
            a.name === savedAgent ||
            a.name.toLowerCase() === savedAgent.toLowerCase()
        );
        if (agent) {
            const selected = document.querySelector('#agentSelect .select-selected');
            const selectedText = selected.querySelector('.select-selected-text');
            selectedText.textContent = agent.name || agent.id;
            selected.dataset.value = agent.id;
            AppState.selectedAgent = agent.id;
        }
    }
}