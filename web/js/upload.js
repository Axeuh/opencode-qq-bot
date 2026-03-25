/**
 * 文件上传模块
 * 处理文件拖放、粘贴、预览和上传
 */

import { AppState } from './state.js';
import { uploadFile } from './api.js';
import { escapeHtml, formatFileSize, readFileAsDataURL, getDOM } from './utils.js';

/**
 * 添加待上传文件
 * @param {File} file - 文件对象
 */
export async function addPendingFile(file) {
    // 检查文件大小（50MB）
    if (file.size > 50 * 1024 * 1024) {
        alert('文件大小不能超过50MB');
        return;
    }
    
    // 生成预览
    let preview = '';
    if (file.type.startsWith('image/')) {
        preview = await readFileAsDataURL(file);
    } else {
        preview = '\uD83D\uDCC4';  // 文件图标
    }
    
    // 添加到待上传列表
    AppState.pendingFiles.push({
        file: file,
        preview: preview,
        type: file.type,
        name: file.name,
        size: file.size
    });
    
    // 更新预览区域
    renderFilePreview();
}

/**
 * 渲染文件预览
 */
export function renderFilePreview() {
    const area = getDOM('filePreviewArea');
    
    if (AppState.pendingFiles.length === 0) {
        area.style.display = 'none';
        area.innerHTML = '';
        return;
    }
    
    area.style.display = 'flex';
    area.innerHTML = AppState.pendingFiles.map((f, i) => `
        <div class="file-preview-card">
            ${f.type.startsWith('image/') ?
                `<img src="${f.preview}" alt="${escapeHtml(f.name)}">` :
                `<div style="width:40px;height:40px;display:flex;align-items:center;justify-content:center;font-size:24px;">${f.preview}</div>`
            }
            <div class="file-info">
                <div class="file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</div>
                <div class="file-size">${formatFileSize(f.size)}</div>
            </div>
            <button class="remove-btn" onclick="window.removePendingFile(${i})">x</button>
        </div>
    `).join('');
}

/**
 * 移除待上传文件
 * @param {number} index - 文件索引
 */
export function removePendingFile(index) {
    AppState.pendingFiles.splice(index, 1);
    renderFilePreview();
}

/**
 * 上传所有待上传文件
 * @returns {Promise<Array>} 上传结果数组
 */
export async function uploadPendingFiles() {
    const uploadedFiles = [];
    
    for (const pf of AppState.pendingFiles) {
        try {
            const result = await uploadFile(pf.file, AppState.userQQ);
            if (result.success) {
                uploadedFiles.push(result);
            } else {
                console.error('[上传] 文件上传失败:', result.error);
            }
        } catch (e) {
            console.error('[上传] 上传失败:', e);
        }
    }
    
    // 清空待上传列表
    AppState.pendingFiles = [];
    renderFilePreview();
    
    return uploadedFiles;
}

/**
 * 初始化拖拽上传
 */
export function initDragDrop() {
    const inputArea = document.querySelector('.input-area');
    
    inputArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        inputArea.classList.add('drag-over');
    });
    
    inputArea.addEventListener('dragleave', (e) => {
        inputArea.classList.remove('drag-over');
    });
    
    inputArea.addEventListener('drop', async (e) => {
        e.preventDefault();
        inputArea.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        for (const file of files) {
            await addPendingFile(file);
        }
    });
}

/**
 * 初始化粘贴图片
 */
export function initPasteImage() {
    document.addEventListener('paste', async (e) => {
        const items = e.clipboardData.items;
        for (const item of items) {
            if (item.type.startsWith('image/')) {
                const file = item.getAsFile();
                await addPendingFile(file);
            }
        }
    });
}