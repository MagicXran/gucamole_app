(function(root) {
    var _users = [];

    function _quotaBytesToLabel(bytes) {
        if (!bytes) return '默认(10GB)';
        var gb = bytes / 1073741824;
        if (gb >= 9000) return '不限制';
        if (gb <= 5) return '5 GB';
        if (gb <= 10) return '10 GB';
        if (gb <= 20) return '20 GB';
        if (gb <= 50) return '50 GB';
        if (gb <= 100) return '100 GB';
        return '不限制';
    }

    function _quotaLabelToGb(label) {
        if (label === '不限制') return 9999;
        if (label === '默认(10GB)') return 0;
        var m = label.match(/(\d+)/);
        return m ? parseInt(m[1]) : 0;
    }

    async function loadUsers() {
        try {
            _users = await api('GET', '/users');
            renderUsersTable();
        } catch (e) { showToast('加载用户失败: ' + e.message, 'error'); }
    }

    function renderUsersTable() {
        var tbody = document.querySelector('#users-table tbody');
        tbody.innerHTML = '';
        _users.forEach(function(u) {
            var tr = document.createElement('tr');

            var idTd = document.createElement('td');
            idTd.textContent = u.id;
            tr.appendChild(idTd);

            var unameTd = document.createElement('td');
            unameTd.textContent = u.username;
            tr.appendChild(unameTd);

            var dnameTd = document.createElement('td');
            dnameTd.textContent = u.display_name;
            tr.appendChild(dnameTd);

            var roleTd = document.createElement('td');
            if (u.is_admin) {
                var adminBadge = document.createElement('span');
                adminBadge.className = 'badge badge--admin';
                adminBadge.textContent = '管理员';
                roleTd.appendChild(adminBadge);
            } else {
                roleTd.textContent = '普通用户';
            }
            tr.appendChild(roleTd);

            var spaceTd = document.createElement('td');
            spaceTd.style.fontSize = '0.82rem';
            spaceTd.style.color = '#555';
            spaceTd.textContent = (u.used_display || '0 B') + ' / ' + (u.quota_display || '-');
            tr.appendChild(spaceTd);

            var statusTd = document.createElement('td');
            var badge = document.createElement('span');
            badge.className = 'badge ' + (u.is_active ? 'badge--active' : 'badge--inactive');
            badge.textContent = u.is_active ? '正常' : '已禁用';
            statusTd.appendChild(badge);
            tr.appendChild(statusTd);

            var actionTd = document.createElement('td');
            var editBtn = document.createElement('button');
            editBtn.className = 'btn btn--outline btn--small';
            editBtn.textContent = '编辑';
            editBtn.onclick = function() { showUserModal(u); };
            actionTd.appendChild(editBtn);

            if (u.is_active) {
                var delBtn = document.createElement('button');
                delBtn.className = 'btn btn--danger btn--small';
                delBtn.style.marginLeft = '0.3rem';
                delBtn.textContent = '禁用';
                delBtn.onclick = function() { deleteUser(u.id); };
                actionTd.appendChild(delBtn);
            }
            tr.appendChild(actionTd);

            tbody.appendChild(tr);
        });
    }

    function showUserModal(u) {
        var isEdit = !!u;
        var title = isEdit ? '编辑用户' : '新建用户';

        var html = '<div class="modal-overlay" onclick="closeModal(event)">' +
            '<div class="modal" onclick="event.stopPropagation()">' +
            '<div class="modal__title">' + escapeHtml(title) + '</div>' +
            '<form id="user-form">' +
            (isEdit ? '<div class="form-group"><label>用户名</label><input type="text" value="' + escapeAttr(u.username) + '" disabled></div>' :
                formGroup('用户名', 'user-username', '', 'text', true)) +
            formGroup(isEdit ? '新密码（留空不改）' : '密码', 'user-password', '', 'password', !isEdit) +
            formGroup('显示名称', 'user-display', isEdit ? u.display_name : '') +
            formGroupSelect('个人空间配额', 'user-quota', ['默认(10GB)', '5 GB', '10 GB', '20 GB', '50 GB', '100 GB', '不限制'],
                isEdit && u.quota_bytes ? _quotaBytesToLabel(u.quota_bytes) : '默认(10GB)') +
            '<div class="form-group form-group--checkbox">' +
            '<input type="checkbox" id="user-is-admin"' + (isEdit && u.is_admin ? ' checked' : '') + '>' +
            '<label for="user-is-admin">管理员</label>' +
            '</div>' +
            (isEdit ? '<div class="form-group form-group--checkbox">' +
            '<input type="checkbox" id="user-is-active"' + (u.is_active ? ' checked' : '') + '>' +
            '<label for="user-is-active">启用</label></div>' : '') +
            '<div class="modal__actions">' +
            '<button type="button" class="btn btn--outline" onclick="closeModal()">取消</button>' +
            '<button type="submit" class="btn btn--primary">' + (isEdit ? '保存' : '创建') + '</button>' +
            '</div>' +
            '</form></div></div>';

        document.getElementById('modal-container').innerHTML = html;
        document.getElementById('user-form').onsubmit = function(e) {
            e.preventDefault();
            saveUser(isEdit ? u.id : null);
        };
    }

    async function saveUser(userId) {
        var data = {};

        var quotaVal = document.getElementById('user-quota').value;
        data.quota_gb = _quotaLabelToGb(quotaVal);

        if (userId) {
            var pw = document.getElementById('user-password').value;
            if (pw) data.password = pw;
            data.display_name = document.getElementById('user-display').value.trim();
            data.is_admin = document.getElementById('user-is-admin').checked;
            var activeEl = document.getElementById('user-is-active');
            if (activeEl) data.is_active = activeEl.checked;
        } else {
            data.username = document.getElementById('user-username').value.trim();
            data.password = document.getElementById('user-password').value;
            data.display_name = document.getElementById('user-display').value.trim();
            data.is_admin = document.getElementById('user-is-admin').checked;

            if (!data.username || !data.password) {
                showToast('用户名和密码为必填项', 'error');
                return;
            }
        }

        try {
            if (userId) {
                await api('PUT', '/users/' + userId, data);
                showToast('用户已更新');
            } else {
                await api('POST', '/users', data);
                showToast('用户已创建');
            }
            closeModal();
            loadUsers();
        } catch (e) { showToast(e.message, 'error'); }
    }

    async function deleteUser(id) {
        if (!confirm('确定要禁用此用户？')) return;
        try {
            await api('DELETE', '/users/' + id);
            showToast('用户已禁用');
            loadUsers();
        } catch (e) { showToast(e.message, 'error'); }
    }

    root.AdminUserUi = {
        loadUsers: loadUsers,
        renderUsersTable: renderUsersTable,
        showUserModal: showUserModal,
        saveUser: saveUser,
        deleteUser: deleteUser,
        _quotaBytesToLabel: _quotaBytesToLabel,
        _quotaLabelToGb: _quotaLabelToGb,
    };
})(typeof window !== 'undefined' ? window : globalThis);
