(function(global) {
    'use strict';

    async function loadAcl() {
        try {
            var users = await api('GET', '/users');
            var apps = await api('GET', '/apps');
            var activeUsers = users.filter(function(u) { return u.is_active; });
            var activeApps = apps.filter(function(a) { return a.is_active; });

            var aclMap = {};
            for (var i = 0; i < activeUsers.length; i++) {
                var aclData = await api('GET', '/users/' + activeUsers[i].id + '/acl');
                aclMap[activeUsers[i].id] = aclData.app_ids || [];
            }

            renderAclMatrix(activeUsers, activeApps, aclMap);
        } catch (e) { showToast('加载权限失败: ' + e.message, 'error'); }
    }

    function renderAclMatrix(users, apps, aclMap) {
        var container = document.getElementById('acl-content');
        container.innerHTML = '';

        if (!users.length || !apps.length) {
            container.textContent = '暂无活跃用户或应用';
            return;
        }

        var table = document.createElement('table');
        table.className = 'acl-matrix';

        var thead = document.createElement('thead');
        var headerRow = document.createElement('tr');
        var th0 = document.createElement('th');
        th0.textContent = '用户 \\ 应用';
        headerRow.appendChild(th0);
        apps.forEach(function(app) {
            var th = document.createElement('th');
            th.textContent = app.name;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        var tbody = document.createElement('tbody');
        users.forEach(function(user) {
            var tr = document.createElement('tr');
            var nameTd = document.createElement('td');
            nameTd.textContent = user.display_name || user.username;
            tr.appendChild(nameTd);

            var userAcl = aclMap[user.id] || [];
            apps.forEach(function(app) {
                var td = document.createElement('td');
                var cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.checked = userAcl.indexOf(app.id) !== -1;
                cb.setAttribute('data-user-id', user.id);
                cb.setAttribute('data-app-id', app.id);
                td.appendChild(cb);
                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        container.appendChild(table);

        var saveBar = document.createElement('div');
        saveBar.className = 'acl-save-bar';
        var saveBtn = document.createElement('button');
        saveBtn.className = 'btn btn--primary';
        saveBtn.textContent = '保存权限';
        saveBtn.onclick = function() { saveAcl(users, apps); };
        saveBar.appendChild(saveBtn);
        container.appendChild(saveBar);
    }

    async function saveAcl(users, apps) {
        try {
            for (var i = 0; i < users.length; i++) {
                var userId = users[i].id;
                var appIds = [];
                var checkboxes = document.querySelectorAll('input[data-user-id="' + userId + '"]');
                checkboxes.forEach(function(cb) {
                    if (cb.checked) appIds.push(parseInt(cb.getAttribute('data-app-id')));
                });
                await api('PUT', '/users/' + userId + '/acl', { app_ids: appIds });
            }
            showToast('权限已保存');
        } catch (e) { showToast('保存权限失败: ' + e.message, 'error'); }
    }

    global.AdminAclUi = {
        loadAcl: loadAcl,
        renderAclMatrix: renderAclMatrix,
        saveAcl: saveAcl,
    };
})(window);
