/**
 * 登录认证模块
 * 处理用户登录、密码设置、登出等功能
 */

import { AppState } from './state.js';
import { apiPost } from './api.js';
import { showModal, hideModal, getDOM } from './utils.js';

// 待设置密码的QQ号
let pendingQQ = null;

/**
 * 处理登录
 */
export async function handleLogin() {
    const qqInput = getDOM('loginQQ');
    const passwordInput = getDOM('loginPassword');
    const loginBtn = document.querySelector('#loginModal .btn-save');
    const qq = qqInput.value.trim();
    const password = passwordInput.value;
    
    if (!qq) {
        alert('请输入 QQ 号');
        return;
    }
    
    if (!/^\d{5,11}$/.test(qq)) {
        alert('请输入有效的 QQ 号 (5-11位数字)');
        return;
    }
    
    loginBtn.disabled = true;
    loginBtn.textContent = '验证中...';
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ qq_id: qq, password: password })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // 登录成功
            localStorage.setItem('userQQ', qq);
            if (result.token) {
                localStorage.setItem('sessionToken', result.token);
            }
            AppState.userQQ = qq;
            AppState.userName = qq;
            
            hideModal('loginModal');
            updateUserName(qq);
            
            // 重置登录表单
            passwordInput.value = '';
            loginBtn.textContent = '登录';
            
            // 触发初始化回调
            if (window.onLoginSuccess) {
                window.onLoginSuccess();
            }
        } else if (result.need_set_password) {
            // 需要设置密码
            pendingQQ = qq;
            hideModal('loginModal');
            showModal('setPasswordModal');
            loginBtn.textContent = '登录';
        } else if (result.need_password) {
            // 需要输入密码
            loginBtn.textContent = '登录';
            if (result.error) {
                alert(result.error);
            }
        } else {
            alert(result.error || '登录失败');
            loginBtn.textContent = '登录';
        }
    } catch (error) {
        console.error('登录请求失败:', error);
        alert('网络错误，请稍后重试');
        loginBtn.textContent = '登录';
    } finally {
        loginBtn.disabled = false;
    }
}

/**
 * 设置密码（首次）
 */
export async function handleSetPassword() {
    const newPassword = getDOM('newPassword').value;
    const confirmPassword = getDOM('confirmPassword').value;
    const setBtn = document.querySelector('#setPasswordModal .btn-save');
    
    if (!newPassword || newPassword.length < 6) {
        alert('密码长度至少6位');
        return;
    }
    
    if (newPassword !== confirmPassword) {
        alert('两次输入的密码不一致');
        return;
    }
    
    setBtn.disabled = true;
    setBtn.textContent = '设置中...';
    
    try {
        const response = await fetch('/api/password/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ qq_id: pendingQQ, password: newPassword })
        });
        
        const result = await response.json();
        
        if (result.success) {
            if (result.token) {
                localStorage.setItem('sessionToken', result.token);
            }
            localStorage.setItem('userQQ', pendingQQ);
            AppState.userQQ = pendingQQ;
            AppState.userName = pendingQQ;
            
            hideModal('setPasswordModal');
            
            // 清空密码输入
            getDOM('newPassword').value = '';
            getDOM('confirmPassword').value = '';
            
            updateUserName(pendingQQ);
            pendingQQ = null;
            
            if (window.onLoginSuccess) {
                window.onLoginSuccess();
            }
        } else {
            alert(result.error || '设置密码失败');
        }
    } catch (error) {
        console.error('设置密码失败:', error);
        alert('网络错误，请稍后重试');
    } finally {
        setBtn.disabled = false;
        setBtn.textContent = '确认设置';
    }
}

/**
 * 修改密码
 */
export async function handleChangePassword() {
    const oldPassword = getDOM('oldPassword').value;
    const newPassword = getDOM('changeNewPassword').value;
    const confirmPassword = getDOM('changeConfirmPassword').value;
    const changeBtn = document.querySelector('#changePasswordModal .btn-save');
    
    if (!oldPassword) {
        alert('请输入原密码');
        return;
    }
    
    if (!newPassword || newPassword.length < 6) {
        alert('新密码长度至少6位');
        return;
    }
    
    if (newPassword !== confirmPassword) {
        alert('两次输入的新密码不一致');
        return;
    }
    
    changeBtn.disabled = true;
    changeBtn.textContent = '修改中...';
    
    try {
        const response = await fetch('/api/password/change', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                qq_id: AppState.userQQ,
                old_password: oldPassword,
                new_password: newPassword
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('密码修改成功');
            hideModal('changePasswordModal');
            
            // 清空密码输入
            getDOM('oldPassword').value = '';
            getDOM('changeNewPassword').value = '';
            getDOM('changeConfirmPassword').value = '';
        } else {
            alert(result.error || '修改密码失败');
        }
    } catch (error) {
        console.error('修改密码失败:', error);
        alert('网络错误，请稍后重试');
    } finally {
        changeBtn.disabled = false;
        changeBtn.textContent = '确认修改';
    }
}

/**
 * 登出
 */
export function handleLogout() {
    localStorage.removeItem('userQQ');
    localStorage.removeItem('sessionToken');
    AppState.userQQ = null;
    AppState.currentSession = null;
    
    // 断开 SSE
    if (AppState.eventSource) {
        AppState.eventSource.close();
        AppState.eventSource = null;
    }
    
    // 重置界面
    getDOM('userName').textContent = 'Guest';
    getDOM('userAvatar').src = 'https://api.dicebear.com/7.x/bottts/svg?seed=Guest&backgroundColor=89CFF0';
    getDOM('sessionList').innerHTML = '';
    getDOM('messageHeader').style.display = 'none';
    getDOM('messageContent').innerHTML = `
        <div class="empty-state" id="emptyState">
            <i class="fas fa-comments"></i>
            <p>选择一个会话开始聊天</p>
            <p style="font-size: 12px; margin-top: 8px;">或点击「新建会话」开始新对话</p>
        </div>
    `;
    
    hideModal('settingsModal');
    showModal('loginModal');
    
    getDOM('chatInput').disabled = true;
    getDOM('sendBtn').disabled = true;
}

/**
 * 更新用户信息显示
 * @param {string} qq - QQ号
 */
export function updateUserName(qq) {
    getDOM('userName').textContent = `QQ: ${qq}`;
    getDOM('userAvatar').src = `https://q1.qlogo.cn/g?b=qq&nk=${qq}&s=100`;
    getDOM('currentQQ').value = qq;
    
    // 获取QQ昵称
    fetch(`/api/qq/userinfo/${qq}`)
        .then(res => res.json())
        .then(data => {
            if (data.success && data.nickname) {
                AppState.userName = data.nickname;
                getDOM('userName').textContent = data.nickname;
            }
        })
        .catch(err => console.error('[QQ] 获取昵称失败:', err));
}

// 导出pendingQQ供外部使用
export function getPendingQQ() {
    return pendingQQ;
}