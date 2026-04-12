(function(global) {
    'use strict';

    var _auditPage = 1;

    var ACTION_LABELS = {
        'login': '登录',
        'login_failed': '登录失败',
        'launch_app': '启动应用',
        'admin_create_app': '创建应用',
        'admin_update_app': '修改应用',
        'admin_delete_app': '禁用应用',
        'admin_create_user': '创建用户',
        'admin_update_user': '修改用户',
        'admin_delete_user': '禁用用户',
        'admin_update_acl': '修改权限',
        'file_upload': '上传文件',
        'file_download': '下载文件',
        'file_delete': '删除文件',
    };

    async function loadAuditLogs(page) {
        _auditPage = page || 1;
        var params = 'page=' + _auditPage + '&page_size=20';

        var username = document.getElementById('filter-username').value.trim();
        var action = document.getElementById('filter-action').value;
        var dateStart = document.getElementById('filter-date-start').value;
        var dateEnd = document.getElementById('filter-date-end').value;

        if (username) params += '&username=' + encodeURIComponent(username);
        if (action) params += '&action=' + encodeURIComponent(action);
        if (dateStart) params += '&date_start=' + dateStart;
        if (dateEnd) params += '&date_end=' + dateEnd;

        try {
            var data = await api('GET', '/audit-logs?' + params);
            renderAuditTable(data.items);
            renderAuditPagination(data.total, data.page, data.page_size);
        } catch (e) { showToast('加载审计日志失败: ' + e.message, 'error'); }
    }

    function renderAuditTable(items) {
        var tbody = document.querySelector('#audit-table tbody');
        tbody.innerHTML = '';

        if (!items || !items.length) {
            var tr = document.createElement('tr');
            var td = document.createElement('td');
            td.colSpan = 6;
            td.style.textAlign = 'center';
            td.style.color = '#999';
            td.textContent = '暂无记录';
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }

        items.forEach(function(log) {
            var tr = document.createElement('tr');

            var timeTd = document.createElement('td');
            timeTd.textContent = log.created_at || '';
            timeTd.style.fontSize = '0.8rem';
            tr.appendChild(timeTd);

            var userTd = document.createElement('td');
            userTd.textContent = log.username;
            tr.appendChild(userTd);

            var actionTd = document.createElement('td');
            actionTd.textContent = ACTION_LABELS[log.action] || log.action;
            tr.appendChild(actionTd);

            var targetTd = document.createElement('td');
            targetTd.textContent = log.target_name || '-';
            tr.appendChild(targetTd);

            var ipTd = document.createElement('td');
            ipTd.textContent = log.ip_address || '-';
            ipTd.style.fontSize = '0.8rem';
            tr.appendChild(ipTd);

            var detailTd = document.createElement('td');
            detailTd.textContent = log.detail || '-';
            detailTd.style.fontSize = '0.8rem';
            detailTd.style.maxWidth = '200px';
            detailTd.style.overflow = 'hidden';
            detailTd.style.textOverflow = 'ellipsis';
            detailTd.style.whiteSpace = 'nowrap';
            tr.appendChild(detailTd);

            tbody.appendChild(tr);
        });
    }

    function renderAuditPagination(total, page, pageSize) {
        var el = document.getElementById('audit-pagination');
        el.innerHTML = '';

        var totalPages = Math.ceil(total / pageSize) || 1;

        if (page > 1) {
            var prevBtn = document.createElement('button');
            prevBtn.className = 'btn btn--outline btn--small';
            prevBtn.textContent = '上一页';
            prevBtn.onclick = function() { loadAuditLogs(page - 1); };
            el.appendChild(prevBtn);
        }

        var info = document.createElement('span');
        info.textContent = '第 ' + page + ' / ' + totalPages + ' 页 (共 ' + total + ' 条)';
        el.appendChild(info);

        if (page < totalPages) {
            var nextBtn = document.createElement('button');
            nextBtn.className = 'btn btn--outline btn--small';
            nextBtn.textContent = '下一页';
            nextBtn.onclick = function() { loadAuditLogs(page + 1); };
            el.appendChild(nextBtn);
        }
    }

    global.AdminAuditUi = {
        ACTION_LABELS: ACTION_LABELS,
        loadAuditLogs: loadAuditLogs,
        renderAuditTable: renderAuditTable,
        renderAuditPagination: renderAuditPagination,
    };
})(window);
