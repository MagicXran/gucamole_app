(function(global) {
    'use strict';

    var _workerGroups = [];
    var _workerNodes = [];

    function _getWorkerGroups() {
        if (Array.isArray(global._workerGroups)) return global._workerGroups;
        return _workerGroups;
    }

    function _setWorkerGroups(items) {
        _workerGroups = Array.isArray(items) ? items : [];
        if (Array.isArray(global._workerGroups)) {
            global._workerGroups = _workerGroups;
        }
    }

    function _getWorkerNodes() {
        if (Array.isArray(global._workerNodes)) return global._workerNodes;
        return _workerNodes;
    }

    function _setWorkerNodes(items) {
        _workerNodes = Array.isArray(items) ? items : [];
        if (Array.isArray(global._workerNodes)) {
            global._workerNodes = _workerNodes;
        }
    }

    function buildGuideCards() {
        return [
            {
                step: 'Step 1',
                title: '先建节点组',
                desc: '把“同一类软件环境”的机器归成一组。一个组通常对应一类求解器、许可证或镜像模板，而不是一台机器。',
            },
            {
                step: 'Step 2',
                title: '再预建节点',
                desc: '每个节点就是一台真实 Windows 主机。主机名必须和机器实际 hostname 一致，共享工作区和 scratch 路径也必须真实可访问。',
            },
            {
                step: 'Step 3',
                title: '最后绑应用',
                desc: '在应用里启用脚本模式，然后选择软件预设、执行器和 Worker 组。客户真正关心的是“这个应用会被派到哪类机器上执行”。',
            },
        ];
    }

    function renderWorkerGuide() {
        var el = document.getElementById('worker-guide');
        if (!el) return;
        var cards = buildGuideCards();
        el.innerHTML = cards.map(function(card) {
            return '<div class="guide-card">' +
                '<div class="guide-card__step">' + escapeHtml(card.step) + '</div>' +
                '<div class="guide-card__title">' + escapeHtml(card.title) + '</div>' +
                '<div class="guide-card__desc">' + escapeHtml(card.desc) + '</div>' +
                '</div>';
        }).join('');
    }

    function describeNodeReadiness(node) {
        var status = String(node.status || '');
        var enrollmentStatus = String(node.latest_enrollment_status || '');
        var ready = Number(node.software_ready_count || 0);
        var total = Number(node.software_total_count || 0);
        var summary = status || 'unknown';
        var tone = status === 'active' ? 'badge--active' : 'badge--inactive';
        var detail = [];

        if (status === 'pending_enrollment') {
            summary = '待注册';
            detail.push('先签发注册码，再去对应 Windows 主机注册');
        } else if (status === 'active') {
            summary = '在线';
            detail.push('最近心跳：' + (node.last_heartbeat_at || '未上报'));
        } else if (status === 'offline') {
            summary = '离线';
            detail.push('最后心跳：' + (node.last_heartbeat_at || '未上报'));
        } else if (status === 'revoked') {
            summary = '已吊销';
            detail.push('当前凭证已失效，需要重新签发');
        }

        if (enrollmentStatus) {
            detail.push('注册码：' + enrollmentStatus + (node.latest_enrollment_expires_at ? ('，到期 ' + node.latest_enrollment_expires_at) : ''));
        }
        if (total > 0) {
            detail.push('软件就绪：' + ready + '/' + total);
        } else {
            detail.push('软件能力：尚未上报');
        }
        if (node.last_error) {
            detail.push('最近错误：' + node.last_error);
        }

        return {
            summary: summary,
            tone: tone,
            detail: detail.join(' · '),
        };
    }

    async function ensureWorkerGroupsLoaded() {
        var groups = _getWorkerGroups();
        if (groups.length) return;
        var data = await api('GET', '/workers/groups');
        _setWorkerGroups((data && data.items) ? data.items : []);
    }

    async function loadWorkers() {
        try {
            var groupsData = await api('GET', '/workers/groups');
            var nodesData = await api('GET', '/workers/nodes');
            _setWorkerGroups((groupsData && groupsData.items) ? groupsData.items : []);
            _setWorkerNodes((nodesData && nodesData.items) ? nodesData.items : []);
            renderWorkerGuide();
            renderWorkerGroupsTable();
            renderWorkerNodesTable();
        } catch (e) { showToast('加载 Worker 失败: ' + e.message, 'error'); }
    }

    function renderWorkerGroupsTable() {
        var tbody = document.querySelector('#worker-groups-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        var groups = _getWorkerGroups();
        if (!groups.length) {
            var emptyTr = document.createElement('tr');
            emptyTr.innerHTML = '<td colspan="5" style="text-align:center;color:#999;">暂无节点组</td>';
            tbody.appendChild(emptyTr);
            return;
        }
        groups.forEach(function(group) {
            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td>' + group.id + '</td>' +
                '<td>' + escapeHtml(group.group_key) + '</td>' +
                '<td>' + escapeHtml(group.name) + '</td>' +
                '<td>' + escapeHtml((group.active_node_count || 0) + ' 在线 / ' + (group.node_count || 0) + ' 总数') + '</td>' +
                '<td>' + escapeHtml(group.description || '-') + '</td>' +
                '<td>' + (group.is_active ? '<span class="badge badge--active">启用</span>' : '<span class="badge badge--inactive">禁用</span>') + '</td>';
            tbody.appendChild(tr);
        });
    }

    function renderWorkerNodesTable() {
        var tbody = document.querySelector('#worker-nodes-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        var nodes = _getWorkerNodes();
        if (!nodes.length) {
            var emptyTr = document.createElement('tr');
            emptyTr.innerHTML = '<td colspan="8" style="text-align:center;color:#999;">暂无节点</td>';
            tbody.appendChild(emptyTr);
            return;
        }
        nodes.forEach(function(node) {
            var softwareReady = Number(node.software_ready_count || 0);
            var softwareTotal = Number(node.software_total_count || 0);
            var softwareSummary = softwareTotal ? (softwareReady + '/' + softwareTotal + ' 就绪') : '未上报';
            var readiness = describeNodeReadiness(node);
            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td>' + node.id + '</td>' +
                '<td><div class="status-stack"><strong>' + escapeHtml(node.display_name || ('worker_' + node.id)) + '</strong><span class="status-stack__meta">' + escapeHtml(node.expected_hostname || '-') + '</span></div></td>' +
                '<td>' + escapeHtml(node.group_name || '-') + '</td>' +
                '<td><div class="status-stack"><span class="badge ' + readiness.tone + '">' + escapeHtml(readiness.summary) + '</span><span class="status-stack__meta">' + escapeHtml(readiness.detail) + '</span></div></td>' +
                '<td><div class="path-stack">工作区：<code>' + escapeHtml(node.workspace_share || '-') + '</code><br>Scratch：<code>' + escapeHtml(node.scratch_root || '-') + '</code><br>并发：' + escapeHtml(String(node.max_concurrent_tasks || 1)) + '</div></td>' +
                '<td><div class="status-stack"><strong>' + escapeHtml(softwareSummary) + '</strong><span class="status-stack__meta">能力详情里可看每个软件的 issues</span></div></td>' +
                '<td>' +
                    '<button class="btn btn--outline btn--small" onclick="showWorkerSoftwareInventory(' + node.id + ')">能力详情</button>' +
                    '<button class="btn btn--outline btn--small" onclick="issueWorkerEnrollment(' + node.id + ')">签发注册码</button>' +
                    '<button class="btn btn--outline btn--small" style="margin-left:0.3rem;" onclick="rotateWorkerToken(' + node.id + ')">轮换凭证</button>' +
                    '<button class="btn btn--danger btn--small" style="margin-left:0.3rem;" onclick="revokeWorkerNode(' + node.id + ')">吊销</button>' +
                '</td>';
            tbody.appendChild(tr);
        });
    }

    function showWorkerSoftwareInventory(workerNodeId) {
        var nodes = _getWorkerNodes();
        var node = nodes.find(function(item) { return item.id === workerNodeId; }) || null;
        if (!node) return;
        var inventory = node.software_inventory || {};
        var entries = Object.keys(inventory);
        var listHtml = entries.length
            ? entries.map(function(key) {
                var item = inventory[key] || {};
                var issues = Array.isArray(item.issues) && item.issues.length ? item.issues.join(', ') : '无';
                return '<li style="margin-bottom:0.75rem;"><strong>' + escapeHtml(item.software_name || key) + '</strong> · ' +
                    '<span class="' + (item.ready ? 'badge badge--active' : 'badge badge--inactive') + '">' + (item.ready ? '就绪' : '未就绪') + '</span>' +
                    '<div style="font-size:0.8rem;color:#666;margin-top:0.25rem;">' + escapeHtml(issues) + '</div></li>';
            }).join('')
            : '<div style="color:#999;">节点尚未上报软件能力</div>';
        document.getElementById('modal-container').innerHTML =
            '<div class="modal-overlay" onclick="closeModal(event)">' +
            '<div class="modal" onclick="event.stopPropagation()">' +
            '<div class="modal__title">软件能力 · ' + escapeHtml(node.display_name || ('worker_' + node.id)) + '</div>' +
            '<ul style="padding-left:1.2rem;">' + listHtml + '</ul>' +
            '<div class="modal__actions"><button type="button" class="btn btn--primary" onclick="closeModal()">关闭</button></div>' +
            '</div></div>';
    }

    function showWorkerGroupModal() {
        var html = '<div class="modal-overlay" onclick="closeModal(event)">' +
            '<div class="modal" onclick="event.stopPropagation()">' +
            '<div class="modal__title">新建节点组</div>' +
            '<form id="worker-group-form">' +
            formGroup('组键', 'worker-group-key', '', 'text', true, '如 ansys-solver') +
            '<div class="field-hint">组键给系统和脚本看，建议稳定、短小、全英文。它表达的是“这一类环境”，不是一台机器。</div>' +
            formGroup('名称', 'worker-group-name', '', 'text', true) +
            '<div class="field-hint">名称给客户和管理员看，直接写成“ANSYS 求解节点组”“Abaqus 批处理节点组”这种人话。</div>' +
            formGroup('说明', 'worker-group-desc', '', 'text', false) +
            '<div class="field-hint">建议写清楚这组机器承载的软件、许可证或用途，例如“用于 MAPDL 脚本求解，需访问 27000 端口许可证服务”。</div>' +
            formGroup('每次认领批量', 'worker-group-batch', 1, 'number', true) +
            '<div class="field-hint">通常保持 1 就够了。批量认领只有在你明确要让一个 Worker 一次拉多任务时才需要调大。</div>' +
            '<div class="modal__actions">' +
            '<button type="button" class="btn btn--outline" onclick="closeModal()">取消</button>' +
            '<button type="submit" class="btn btn--primary">创建</button>' +
            '</div></form></div></div>';
        document.getElementById('modal-container').innerHTML = html;
        document.getElementById('worker-group-form').onsubmit = function(e) {
            e.preventDefault();
            saveWorkerGroup();
        };
    }

    async function saveWorkerGroup() {
        var data = {
            group_key: document.getElementById('worker-group-key').value.trim(),
            name: document.getElementById('worker-group-name').value.trim(),
            description: document.getElementById('worker-group-desc').value.trim(),
            max_claim_batch: parseInt(document.getElementById('worker-group-batch').value, 10) || 1,
        };
        try {
            await api('POST', '/workers/groups', data);
            showToast('节点组已创建');
            closeModal();
            _setWorkerGroups([]);
            loadWorkers();
        } catch (e) { showToast(e.message, 'error'); }
    }

    async function showWorkerNodeModal() {
        await ensureWorkerGroupsLoaded();
        var groups = _getWorkerGroups();
        if (!groups.length) {
            showToast('请先创建节点组', 'error');
            return;
        }
        var groupOptions = groups.map(function(group) {
            return '<option value="' + group.id + '">' + escapeHtml(group.name) + '</option>';
        }).join('');
        var html = '<div class="modal-overlay" onclick="closeModal(event)">' +
            '<div class="modal" onclick="event.stopPropagation()">' +
            '<div class="modal__title">预建 Worker 节点</div>' +
            '<form id="worker-node-form">' +
            '<div class="form-group"><label>节点组</label><select id="worker-node-group-id">' + groupOptions + '</select></div>' +
            '<div class="field-hint">把这台机器放进哪一类运行环境。应用绑定时选的是节点组，不是单台机器。</div>' +
            formGroup('显示名称', 'worker-node-display-name', '', 'text', true) +
            '<div class="field-hint">这是后台里给人看的名字，建议带上机房/用途，比如 “CAE-ANSYS-01”。</div>' +
            formGroup('期望主机名', 'worker-node-expected-hostname', '', 'text', true, '如 SIM-ANSYS-01') +
            '<div class="field-hint">必须和 Windows 主机执行 <code>hostname</code> 的结果完全一致，否则注册码会被拒绝。</div>' +
            formGroup('本地 scratch 根目录', 'worker-node-scratch-root', 'C:\\sim-work', 'text', true) +
            '<div class="field-hint">脚本会先拷到这里再执行。必须是 Worker 本机可写目录，别填共享盘。</div>' +
            formGroup('共享工作区 UNC', 'worker-node-workspace-share', '\\\\sim-fs\\workspaces', 'text', true) +
            '<div class="field-hint">Portal 用户空间对这台机器暴露出来的共享路径。必须是 Worker 能访问到的共享目录，而不是 Portal 容器里的路径。</div>' +
            formGroup('本机并发上限', 'worker-node-max-concurrent', 1, 'number', true) +
            '<div class="field-hint">保守一点，默认 1。除非你非常确定软件、许可证和机器都支持并发，否则别乱调。</div>' +
            '<div class="modal__actions">' +
            '<button type="button" class="btn btn--outline" onclick="closeModal()">取消</button>' +
            '<button type="submit" class="btn btn--primary">创建</button>' +
            '</div></form></div></div>';
        document.getElementById('modal-container').innerHTML = html;
        document.getElementById('worker-node-form').onsubmit = function(e) {
            e.preventDefault();
            saveWorkerNode();
        };
    }

    async function saveWorkerNode() {
        var data = {
            group_id: parseInt(document.getElementById('worker-node-group-id').value, 10),
            display_name: document.getElementById('worker-node-display-name').value.trim(),
            expected_hostname: document.getElementById('worker-node-expected-hostname').value.trim(),
            scratch_root: document.getElementById('worker-node-scratch-root').value.trim(),
            workspace_share: document.getElementById('worker-node-workspace-share').value.trim(),
            max_concurrent_tasks: parseInt(document.getElementById('worker-node-max-concurrent').value, 10) || 1,
        };
        try {
            await api('POST', '/workers/nodes', data);
            showToast('Worker 节点已预建');
            closeModal();
            loadWorkers();
        } catch (e) { showToast(e.message, 'error'); }
    }

    async function issueWorkerEnrollment(workerNodeId) {
        try {
            var result = await api('POST', '/workers/nodes/' + workerNodeId + '/enrollment', { expires_hours: 24 });
            showToast('注册码已签发，请立即复制');
            document.getElementById('modal-container').innerHTML =
                '<div class="modal-overlay" onclick="closeModal(event)">' +
                '<div class="modal" onclick="event.stopPropagation()">' +
                '<div class="modal__title">Worker 注册码</div>' +
                '<div class="form-group"><label>Enrollment Token</label><input type="text" value="' + escapeAttr(result.plain_token) + '" readonly></div>' +
                '<div class="form-group"><label>过期时间</label><input type="text" value="' + escapeAttr(result.expires_at || '') + '" readonly></div>' +
                '<div class="modal__actions"><button type="button" class="btn btn--primary" onclick="closeModal()">关闭</button></div>' +
                '</div></div>';
        } catch (e) { showToast(e.message, 'error'); }
    }

    async function rotateWorkerToken(workerNodeId) {
        try {
            var result = await api('POST', '/workers/nodes/' + workerNodeId + '/rotate-token');
            document.getElementById('modal-container').innerHTML =
                '<div class="modal-overlay" onclick="closeModal(event)">' +
                '<div class="modal" onclick="event.stopPropagation()">' +
                '<div class="modal__title">新 Worker 凭证</div>' +
                '<div class="form-group"><label>Access Token</label><input type="text" value="' + escapeAttr(result.plain_token) + '" readonly></div>' +
                '<div class="modal__actions"><button type="button" class="btn btn--primary" onclick="closeModal()">关闭</button></div>' +
                '</div></div>';
        } catch (e) { showToast(e.message, 'error'); }
    }

    async function revokeWorkerNode(workerNodeId) {
        if (!confirm('确定吊销这个 Worker 节点？')) return;
        try {
            await api('POST', '/workers/nodes/' + workerNodeId + '/revoke');
            showToast('Worker 已吊销');
            loadWorkers();
        } catch (e) { showToast(e.message, 'error'); }
    }

    var adminWorkerUi = {
        buildGuideCards: buildGuideCards,
        renderWorkerGuide: renderWorkerGuide,
        describeNodeReadiness: describeNodeReadiness,
        ensureWorkerGroupsLoaded: ensureWorkerGroupsLoaded,
        loadWorkers: loadWorkers,
        renderWorkerGroupsTable: renderWorkerGroupsTable,
        renderWorkerNodesTable: renderWorkerNodesTable,
        showWorkerSoftwareInventory: showWorkerSoftwareInventory,
        showWorkerGroupModal: showWorkerGroupModal,
        saveWorkerGroup: saveWorkerGroup,
        showWorkerNodeModal: showWorkerNodeModal,
        saveWorkerNode: saveWorkerNode,
        issueWorkerEnrollment: issueWorkerEnrollment,
        rotateWorkerToken: rotateWorkerToken,
        revokeWorkerNode: revokeWorkerNode,
    };

    var workerUx = global.AdminWorkerUx || {};
    workerUx.buildGuideCards = buildGuideCards;
    workerUx.describeNodeReadiness = describeNodeReadiness;

    global.AdminWorkerUi = adminWorkerUi;
    global.AdminWorkerUx = workerUx;
})(window);
