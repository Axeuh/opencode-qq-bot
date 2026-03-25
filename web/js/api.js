/**
 * API调用封装模块
 * 统一处理HTTP请求和认证
 */

const API_BASE = '';

/**
 * 获取认证token
 * @returns {string} token
 */
export function getAuthToken() {
    return localStorage.getItem('sessionToken') || '';
}

/**
 * 处理401未授权错误
 */
function handleUnauthorized() {
    localStorage.removeItem('sessionToken');
    localStorage.removeItem('userQQ');
    location.reload();
    throw new Error('会话已过期，请重新登录');
}

/**
 * 解析API响应
 * @param {Response} res - fetch响应对象
 * @returns {Promise<any>} 解析后的数据
 */
async function parseResponse(res) {
    if (res.status === 401) {
        handleUnauthorized();
    }
    
    if (!res.ok) {
        let errorMsg = `HTTP ${res.status}`;
        try {
            const errorData = await res.json();
            errorMsg = errorData.error || errorData.message || errorMsg;
        } catch (e) {
            // 无法解析JSON，使用默认错误信息
        }
        throw new Error(errorMsg);
    }
    
    // 检查响应是否为空
    const text = await res.text();
    if (!text || text.trim() === '') {
        return { success: true };
    }
    
    try {
        return JSON.parse(text);
    } catch (e) {
        console.warn('API响应不是有效JSON:', text);
        return { success: true, raw: text };
    }
}

/**
 * GET请求
 * @param {string} url - 请求URL
 * @returns {Promise<any>} 响应数据
 */
export async function apiGet(url) {
    const token = getAuthToken();
    const headers = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const res = await fetch(API_BASE + url, { headers });
    return parseResponse(res);
}

/**
 * POST请求
 * @param {string} url - 请求URL
 * @param {object} body - 请求体
 * @returns {Promise<any>} 响应数据
 */
export async function apiPost(url, body) {
    const token = getAuthToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const res = await fetch(API_BASE + url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
    });
    
    return parseResponse(res);
}

/**
 * DELETE请求
 * @param {string} url - 请求URL
 * @returns {Promise<any>} 响应数据
 */
export async function apiDelete(url) {
    const token = getAuthToken();
    const headers = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const res = await fetch(API_BASE + url, {
        method: 'DELETE',
        headers
    });
    
    if (res.status === 401) {
        handleUnauthorized();
    }
    
    if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
    }
    
    return res.json();
}

/**
 * 上传文件
 * @param {File} file - 文件对象
 * @param {string} userId - 用户ID
 * @returns {Promise<object>} 上传结果
 */
export async function uploadFile(file, userId) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);
    
    const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
    });
    
    return response.json();
}