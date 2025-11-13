// status-page.js: User Management for /status (admin only)
// Renders user table and handles admin actions

document.addEventListener('DOMContentLoaded', async () => {
    const userSection = document.getElementById('user-management-section');
    const userTableDiv = document.getElementById('user-management');
    let isAdmin = false;

    // Check admin status
    try {
        const meRes = await fetch('/api/v1/auth/me', { credentials: 'include' });
        if (meRes.ok) {
            const me = await meRes.json();
            isAdmin = me.is_admin;
        }
    } catch (e) { isAdmin = false; }

    if (!isAdmin) return;
    userSection.style.display = '';
    loadUsers();

    async function loadUsers() {
        userTableDiv.innerHTML = '<div class="text-center py-8"><div class="loading-spinner mx-auto"></div></div>';
        try {
            const res = await fetch('/api/v1/admin/users');
            if (!res.ok) throw new Error('Failed to fetch users');
            const users = await res.json();
            renderTable(users);
        } catch (err) {
            userTableDiv.innerHTML = `<div class="text-red-500 text-center">Error loading users: ${err.message}</div>`;
        }
    }

    function renderTable(users) {
        let html = `<table class="table-auto w-full text-sm border rounded-lg overflow-hidden">
            <thead class="bg-gray-800">
                <tr>
                    <th class="px-4 py-3 text-center">Username</th>
                    <th class="px-4 py-3 text-center">Email</th>
                    <th class="px-4 py-3 text-center">Admin</th>
                    <th class="px-4 py-3 text-center">Premium</th>
                    <th class="px-4 py-3 text-center">Created</th>
                    <th class="px-4 py-3 text-center">Actions</th>
                </tr>
            </thead>
            <tbody>`;
        for (const u of users) {
            // Format dates properly
            let premiumDate = 'No';
            if (u.premium_until) {
                try {
                    // Parse and format date - handle different formats
                    const dateStr = u.premium_until.includes('T') 
                        ? u.premium_until.split('T')[0] 
                        : u.premium_until.split(' ')[0];
                    const [year, month, day] = dateStr.split('-');
                    premiumDate = `${year}-${month}-${day}`;
                } catch (e) {
                    premiumDate = u.premium_until.split(' ')[0];
                }
            }
            
            let createdDate = '-';
            if (u.created_at) {
                try {
                    const dateStr = u.created_at.includes('T')
                        ? u.created_at.split('T')[0]
                        : u.created_at.split(' ')[0];
                    const [year, month, day] = dateStr.split('-');
                    createdDate = `${year}-${month}-${day}`;
                } catch (e) {
                    createdDate = u.created_at.split(' ')[0];
                }
            }
            
            html += `<tr class="border-b border-gray-700 hover:bg-white/5">
                <td class="px-4 py-3 text-center font-medium">${u.username}</td>
                <td class="px-4 py-3 text-center text-gray-300">${u.email}</td>
                <td class="px-4 py-3 text-center">${u.is_admin ? '<span title="Admin" class="text-green-400 text-lg">✔</span>' : '<span class="text-gray-600">—</span>'}</td>
                <td class="px-4 py-3 text-center">${premiumDate !== 'No' ? `<span title="Premium until ${premiumDate}" class="text-cyan-400 font-mono text-xs">${premiumDate}</span>` : '<span class="text-gray-500">No</span>'}</td>
                <td class="px-4 py-3 text-center text-gray-400 font-mono text-xs">${createdDate}</td>
                <td class="px-4 py-3 text-center">
                    <div class="flex gap-2 justify-center">
                        <button class="action-btn" title="Reset Password" onclick="resetPassword(${u.id}, '${u.username}')"><i class="fas fa-key"></i></button>
                        <button class="action-btn" title="Delete User" onclick="deleteUser(${u.id}, '${u.username}')"><i class="fas fa-trash"></i></button>
                        <button class="action-btn" title="Toggle Premium" onclick="togglePremium(${u.id}, '${u.username}')"><i class="fas fa-star"></i></button>
                    </div>
                </td>
            </tr>`;
        }
        html += '</tbody></table>';
        userTableDiv.innerHTML = html;
    }

    window.resetPassword = async function(userId, username) {
        if (!confirm(`Reset password for ${username}?`)) return;
        userTableDiv.innerHTML += '<div class="fade-update text-center">Resetting password...</div>';
        try {
            const res = await fetch(`/api/v1/admin/users/${userId}/reset-password`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                // Show copyable modal with the temporary password
                showPasswordModal(username, data.temp_password);
                // Refresh after showing modal so user list stays current
                loadUsers();
            } else {
                alert('Password reset failed');
            }
        } catch (err) {
            alert('Error: ' + err.message);
        }
    }

    window.deleteUser = async function(userId, username) {
        if (!confirm(`Delete user ${username}? This cannot be undone.`)) return;
        userTableDiv.innerHTML += '<div class="fade-update text-center">Deleting user...</div>';
        try {
            const res = await fetch(`/api/v1/admin/users/${userId}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                alert(`User ${username} deleted.`);
                loadUsers();
            } else {
                alert('User deletion failed');
            }
        } catch (err) {
            alert('Error: ' + err.message);
        }
    }

    window.togglePremium = async function(userId, username) {
        userTableDiv.innerHTML += '<div class="fade-update text-center">Toggling premium...</div>';
        try {
            const res = await fetch(`/api/v1/admin/users/${userId}/premium`, { method: 'PUT' });
            const data = await res.json();
            if (data.success) {
                alert(`Premium status for ${username}: ${data.premium_status}`);
                loadUsers();
            } else {
                alert('Premium toggle failed');
            }
        } catch (err) {
            alert('Error: ' + err.message);
        }
    }
});

// Button styles for actions
const style = document.createElement('style');
style.innerHTML = `
.action-btn { 
    background: rgba(0, 224, 255, 0.1); 
    color: #00e0ff; 
    border: 1px solid rgba(0, 224, 255, 0.3);
    border-radius: 6px; 
    padding: 8px 12px; 
    cursor: pointer; 
    transition: all 0.3s ease;
    font-size: 0.875rem;
}
.action-btn:hover { 
    background: #00e0ff; 
    color: #0d0f1a; 
    border-color: #00e0ff;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 224, 255, 0.4);
}
.action-btn:active {
    transform: translateY(0);
}
`;
document.head.appendChild(style);

// --- Modal utilities for copyable temp password ---
(function ensureModalStyles(){
    const modalStyle = document.createElement('style');
    modalStyle.innerHTML = `
    .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: none; align-items: center; justify-content: center; z-index: 2000; }
    .modal { background: #0f172a; border: 1px solid rgba(255,255,255,0.12); width: 95%; max-width: 520px; border-radius: 12px; box-shadow: 0 20px 50px rgba(0,0,0,0.6); }
    .modal-header { padding: 14px 18px; border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: space-between; }
    .modal-title { font-weight: 600; color: #e2e8f0; }
    .modal-body { padding: 16px 18px; color: #cbd5e1; }
    .modal-footer { padding: 14px 18px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; gap: 10px; justify-content: flex-end; }
    .btn { border: 1px solid rgba(255,255,255,0.15); background: rgba(255,255,255,0.06); color: #e2e8f0; padding: 8px 14px; border-radius: 8px; cursor: pointer; transition: all .2s ease; }
    .btn:hover { background: rgba(255,255,255,0.12); }
    .btn-primary { border-color: #00e0ff; background: rgba(0,224,255,0.12); color: #00e0ff; }
    .btn-primary:hover { background: #00e0ff; color: #0d0f1a; }
    .pw-field { display: flex; gap: 8px; align-items: center; }
    .pw-input { flex: 1; background: #0b1220; border: 1px solid rgba(255,255,255,0.12); color: #e2e8f0; padding: 10px 12px; border-radius: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 14px; }
    .pw-toggle { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); color: #cbd5e1; padding: 8px 10px; border-radius: 8px; cursor: pointer; }
    `;
    document.head.appendChild(modalStyle);
})();

function ensureModalRoot(){
    let root = document.getElementById('admin-modal-root');
    if (!root) {
        root = document.createElement('div');
        root.id = 'admin-modal-root';
        root.className = 'modal-backdrop';
        root.innerHTML = `
            <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
                <div class="modal-header">
                    <div id="modal-title" class="modal-title">Temporary Password</div>
                    <button id="modal-close" class="btn" aria-label="Close">Close</button>
                </div>
                <div class="modal-body">
                    <div class="mb-2 text-sm text-gray-400" id="modal-subtitle"></div>
                    <div class="pw-field">
                        <input id="modal-password" class="pw-input" type="password" readonly value="" />
                        <button id="pw-toggle" class="pw-toggle" title="Show/Hide">👁</button>
                        <button id="pw-copy" class="btn-primary btn" title="Copy">Copy</button>
                    </div>
                    <div id="copy-feedback" class="text-xs text-green-400 mt-2" style="display:none;">Copied to clipboard</div>
                </div>
                <div class="modal-footer">
                    <button id="modal-ok" class="btn-primary btn">OK</button>
                </div>
            </div>`;
        document.body.appendChild(root);

        // Wire close handlers once
        const hide = () => { root.style.display = 'none'; };
        root.addEventListener('click', (e) => { if (e.target === root) hide(); });
        root.querySelector('#modal-close').addEventListener('click', hide);
        root.querySelector('#modal-ok').addEventListener('click', hide);
        // Toggle show/hide password
        const pwInput = root.querySelector('#modal-password');
        root.querySelector('#pw-toggle').addEventListener('click', () => {
            pwInput.type = pwInput.type === 'password' ? 'text' : 'password';
        });
        // Copy to clipboard
        root.querySelector('#pw-copy').addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(pwInput.value);
                const fb = root.querySelector('#copy-feedback');
                fb.style.display = 'block';
                setTimeout(() => fb.style.display = 'none', 1400);
            } catch (e) {
                // Fallback: select text for manual copy
                pwInput.type = 'text';
                pwInput.focus();
                pwInput.select();
            }
        });
    }
    return root;
}

function showPasswordModal(username, password){
    const root = ensureModalRoot();
    root.style.display = 'flex';
    const title = root.querySelector('#modal-title');
    const subtitle = root.querySelector('#modal-subtitle');
    const pwInput = root.querySelector('#modal-password');
    const fb = root.querySelector('#copy-feedback');
    title.textContent = 'Temporary Password';
    subtitle.textContent = `for ${username}`;
    pwInput.type = 'password';
    pwInput.value = password || '';
    fb.style.display = 'none';
}
