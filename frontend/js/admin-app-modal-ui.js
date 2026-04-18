(function(root) {
    var _apps = [];
    var _workerGroups = [];
    var _scriptProfiles = [];

    function _chk(label, id, checked) {
        return '<div class="form-group form-group--checkbox">' +
            '<input type="checkbox" id="' + id + '"' + (checked ? ' checked' : '') + '>' +
            '<label for="' + id + '">' + escapeHtml(label) + '</label></div>';
    }

    function normalizeTriStatePolicy(value) {
        if (value === 1 || value === true || value === '1') return '1';
        if (value === 0 || value === false || value === '0') return '0';
        return '';
    }

    function buildTriStatePolicyOptions(value) {
        var selected = normalizeTriStatePolicy(value);
        return '<option value=""' + (selected === '' ? ' selected' : '') + '>继承全局</option>' +
            '<option value="1"' + (selected === '1' ? ' selected' : '') + '>强制禁用</option>' +
            '<option value="0"' + (selected === '0' ? ' selected' : '') + '>强制允许</option>';
    }

    function parseTriStatePolicy(value) {
        if (value === '1') return 1;
        if (value === '0') return 0;
        return null;
    }

    function buildAppKindOptions(value) {
        var selected = value || 'commercial_software';
        return '<option value="commercial_software"' + (selected === 'commercial_software' ? ' selected' : '') + '>商业软件</option>' +
            '<option value="simulation_app"' + (selected === 'simulation_app' ? ' selected' : '') + '>仿真APP</option>' +
            '<option value="compute_tool"' + (selected === 'compute_tool' ? ' selected' : '') + '>计算工具</option>';
    }

    function formatAttachmentEditorValue(items) {
        return (items || []).map(function(item) {
            var parts = [String(item.title || '').trim()];
            var summary = String(item.summary || '').trim();
            if (summary) parts.push(summary);
            parts.push(String(item.link_url || '').trim());
            return parts.join(' | ');
        }).filter(function(line) { return !!line.trim(); }).join('\n');
    }

    function parseAttachmentEditorValue(value, label) {
        return String(value || '')
            .split(/\r?\n/)
            .map(function(line) { return line.trim(); })
            .filter(function(line) { return !!line; })
            .map(function(line, index) {
                var parts = line.split('|').map(function(part) { return part.trim(); });
                if (parts.length < 2) {
                    throw new Error(label + ' 第 ' + (index + 1) + ' 行格式不对，至少要写“标题 | 链接”');
                }
                var title = parts[0];
                var linkUrl = parts[parts.length - 1];
                var summary = parts.length > 2 ? parts.slice(1, -1).join(' | ') : '';
                if (!title || !linkUrl) {
                    throw new Error(label + ' 第 ' + (index + 1) + ' 行缺标题或链接');
                }
                return {
                    title: title,
                    summary: summary,
                    link_url: linkUrl,
                    sort_order: index,
                };
            });
    }

    function setPoolAttachmentStatus(message, tone) {
        var statusEl = document.getElementById('pool-attachment-status');
        if (!statusEl) return;
        statusEl.className = 'field-hint' + (tone ? ' field-hint--' + tone : '');
        statusEl.textContent = message || '';
    }

    function applyPoolAttachmentPayload(payload) {
        var tutorialEl = document.getElementById('pool-attachment-tutorial-docs');
        var videoEl = document.getElementById('pool-attachment-video-resources');
        var pluginEl = document.getElementById('pool-attachment-plugin-downloads');
        if (tutorialEl) tutorialEl.value = formatAttachmentEditorValue(payload && payload.tutorial_docs);
        if (videoEl) videoEl.value = formatAttachmentEditorValue(payload && payload.video_resources);
        if (pluginEl) pluginEl.value = formatAttachmentEditorValue(payload && payload.plugin_downloads);
    }

    function resolvePoolAttachmentTargetPoolId(poolId) {
        if (poolId) return poolId;
        var boundPoolEl = document.getElementById('pool-attachment-bound-pool-id');
        if (boundPoolEl && boundPoolEl.value) {
            return parseInt(boundPoolEl.value, 10) || null;
        }
        var poolEl = document.getElementById('app-pool-id');
        if (!poolEl || !poolEl.value) return null;
        return parseInt(poolEl.value, 10) || null;
    }

    function refreshPoolAttachmentBindingStatus() {
        var boundPoolEl = document.getElementById('pool-attachment-bound-pool-id');
        if (!boundPoolEl || !boundPoolEl.value) return;
        var boundPoolId = parseInt(boundPoolEl.value, 10) || null;
        var poolEl = document.getElementById('app-pool-id');
        var selectedPoolId = poolEl && poolEl.value ? (parseInt(poolEl.value, 10) || null) : null;
        if (boundPoolId && selectedPoolId && boundPoolId !== selectedPoolId) {
            setPoolAttachmentStatus(
                '你改了 App 的资源池选择，但共享附件仍绑定原资源池 #' + boundPoolId + '。先保存 App 后再改新池附件，别把别的池写脏。',
                'warning'
            );
            return;
        }
        if (boundPoolId) {
            setPoolAttachmentStatus('当前正在编辑资源池 #' + boundPoolId + ' 的共享附件。', 'info');
        }
    }

    async function loadPoolAttachmentEditors(poolId) {
        var targetPoolId = resolvePoolAttachmentTargetPoolId(poolId);
        if (!targetPoolId) {
            setPoolAttachmentStatus('请先选择资源池，再维护共享附件。', 'warning');
            applyPoolAttachmentPayload({
                tutorial_docs: [],
                video_resources: [],
                plugin_downloads: [],
            });
            return null;
        }
        setPoolAttachmentStatus('正在加载当前资源池共享附件...', 'info');
        try {
            var payload = await api('GET', '/pools/' + targetPoolId + '/attachments');
            applyPoolAttachmentPayload(payload || {});
            refreshPoolAttachmentBindingStatus();
            return payload;
        } catch (e) {
            setPoolAttachmentStatus('共享附件加载失败：' + e.message, 'error');
            showToast('加载资源池共享附件失败: ' + e.message, 'error');
            throw e;
        }
    }

    async function savePoolAttachments(poolId, overridePayload) {
        var targetPoolId = resolvePoolAttachmentTargetPoolId(poolId);
        if (!targetPoolId) {
            showToast('请选择资源池后再保存共享附件', 'error');
            return null;
        }
        try {
            var payload = overridePayload || {
                tutorial_docs: parseAttachmentEditorValue(
                    document.getElementById('pool-attachment-tutorial-docs').value,
                    '教程文档'
                ),
                video_resources: parseAttachmentEditorValue(
                    document.getElementById('pool-attachment-video-resources').value,
                    '视频资源'
                ),
                plugin_downloads: parseAttachmentEditorValue(
                    document.getElementById('pool-attachment-plugin-downloads').value,
                    '插件下载'
                ),
            };
            setPoolAttachmentStatus('正在保存当前资源池共享附件...', 'info');
            var result = await api('PUT', '/pools/' + targetPoolId + '/attachments', payload);
            applyPoolAttachmentPayload(result || payload);
            setPoolAttachmentStatus('资源池共享附件已保存。', 'success');
            showToast('资源池附件已保存');
            return result;
        } catch (e) {
            setPoolAttachmentStatus('共享附件保存失败：' + e.message, 'error');
            showToast(e.message, 'error');
            if (/格式不对|缺标题或链接/.test(String(e && e.message || ''))) {
                return null;
            }
            throw e;
        }
    }

    async function clearPoolAttachments(poolId) {
        var targetPoolId = resolvePoolAttachmentTargetPoolId(poolId);
        if (!targetPoolId) {
            showToast('请选择资源池后再清空共享附件', 'error');
            return null;
        }
        if (typeof confirm === 'function' && !confirm('确定清空当前资源池的教程文档 / 视频资源 / 插件下载？')) {
            return null;
        }
        applyPoolAttachmentPayload({
            tutorial_docs: [],
            video_resources: [],
            plugin_downloads: [],
        });
        return savePoolAttachments(targetPoolId, {
            tutorial_docs: [],
            video_resources: [],
            plugin_downloads: [],
        });
    }

    function buildScriptBindingSummary(state) {
        if (!state.script_enabled) {
            return '当前只作为普通 RemoteApp 使用，不会派发到 Worker 节点执行脚本。';
        }
        return '脚本将通过 ' + (state.executor_key || '未选择执行器') +
            ' 执行，并派发到 Worker 组“' + (state.worker_group_name || '未选择节点组') +
            '”，软件预设为“' + (state.profile_name || '未选择软件预设') + '”。';
    }

    async function ensureWorkerGroupsLoaded() {
        if (_workerGroups.length) return;
        var data = await api('GET', '/workers/groups');
        _workerGroups = (data && data.items) ? data.items : [];
    }

    async function ensureScriptProfilesLoaded() {
        if (_scriptProfiles.length) return;
        var data = await api('GET', '/script-profiles');
        _scriptProfiles = (data && data.items) ? data.items : [];
    }

    async function loadApps() {
        try {
            _apps = await api('GET', '/apps');
            renderAppsTable();
        } catch (e) { showToast('加载应用失败: ' + e.message, 'error'); }
    }

    function renderAppsTable() {
        var tbody = document.querySelector('#apps-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        _apps.forEach(function(app) {
            var tr = document.createElement('tr');

            var cells = [
                app.id,
                escapeHtml(app.name),
                escapeHtml(app.hostname),
                app.port,
                escapeHtml(app.remote_app || '-'),
                app.script_enabled ? ('已启用 · ' + escapeHtml(app.script_executor_key || '-')) : '未启用',
            ];
            cells.forEach(function(val) {
                var td = document.createElement('td');
                td.textContent = val;
                tr.appendChild(td);
            });

            var statusTd = document.createElement('td');
            var badge = document.createElement('span');
            badge.className = 'badge ' + (app.is_active ? 'badge--active' : 'badge--inactive');
            badge.textContent = app.is_active ? '启用' : '禁用';
            statusTd.appendChild(badge);
            tr.appendChild(statusTd);

            var actionTd = document.createElement('td');
            var editBtn = document.createElement('button');
            editBtn.className = 'btn btn--outline btn--small';
            editBtn.textContent = '编辑';
            editBtn.onclick = function() { showAppModal(app); };
            actionTd.appendChild(editBtn);

            if (app.is_active) {
                var delBtn = document.createElement('button');
                delBtn.className = 'btn btn--danger btn--small';
                delBtn.style.marginLeft = '0.3rem';
                delBtn.textContent = '禁用';
                delBtn.onclick = function() { deleteApp(app.id); };
                actionTd.appendChild(delBtn);
            }
            tr.appendChild(actionTd);

            tbody.appendChild(tr);
        });
    }

    async function deleteApp(id) {
        if (!confirm('确定要禁用此应用？')) return;
        try {
            await api('DELETE', '/apps/' + id);
            showToast('应用已禁用');
            loadApps();
        } catch (e) { showToast(e.message, 'error'); }
    }

    function findScriptProfile(profileKey) {
        return _scriptProfiles.find(function(item) { return item.profile_key === profileKey; }) || null;
    }

    function updateScriptProfileHint(profileKey) {
        var hintEl = document.getElementById('app-script-profile-desc');
        if (!hintEl) return;
        var profile = findScriptProfile(profileKey);
        hintEl.textContent = profile ? (profile.description || profile.display_name) : '未选择软件预设';
    }

    function applySelectedScriptProfile() {
        var selectEl = document.getElementById('app-script-profile-key');
        if (!selectEl) return;
        var profile = findScriptProfile(selectEl.value);
        updateScriptProfileHint(selectEl.value);
        if (!profile) return;
        var executorEl = document.getElementById('app-script-executor');
        var pythonEl = document.getElementById('app-script-python-executable');
        var envEl = document.getElementById('app-script-python-env');
        if (executorEl) executorEl.value = profile.executor_key || '';
        if (pythonEl) pythonEl.value = profile.python_executable || '';
        if (envEl) envEl.value = profile.python_env ? JSON.stringify(profile.python_env) : '';
    }

    async function showAppModal(app) {
        await ensurePoolsLoaded();
        await ensureWorkerGroupsLoaded();
        await ensureScriptProfilesLoaded();
        if (!_pools.length) {
            showToast('请先创建资源池，再创建应用', 'error');
            return;
        }
        var isEdit = !!app;
        var title = isEdit ? '编辑应用' : '新建应用';

        var adv = {
            color_depth: app ? app.color_depth : null,
            disable_gfx: app ? app.disable_gfx : true,
            resize_method: app ? (app.resize_method || 'display-update') : 'display-update',
            enable_wallpaper: app ? app.enable_wallpaper : false,
            enable_font_smoothing: app ? (app.enable_font_smoothing !== false && app.enable_font_smoothing !== 0) : true,
            disable_copy: app ? app.disable_copy : false,
            disable_paste: app ? app.disable_paste : false,
            enable_audio: app ? (app.enable_audio !== false && app.enable_audio !== 0) : true,
            enable_audio_input: app ? app.enable_audio_input : false,
            enable_printing: app ? app.enable_printing : false,
            timezone: app ? (app.timezone || '') : '',
            keyboard_layout: app ? (app.keyboard_layout || '') : '',
        };

        var depthOpts = [
            { v: '', l: '自动' },
            { v: '8', l: '8 位 (256色)' },
            { v: '16', l: '16 位 (高彩)' },
            { v: '24', l: '24 位 (真彩)' },
        ];
        var depthVal = adv.color_depth ? String(adv.color_depth) : '';
        var depthSelect = '<div class="form-group"><label>色深</label><select id="app-color-depth">';
        depthOpts.forEach(function(o) {
            depthSelect += '<option value="' + o.v + '"' + (o.v === depthVal ? ' selected' : '') + '>' + o.l + '</option>';
        });
        depthSelect += '</select></div>';

        var tzOpts = ['', 'Asia/Shanghai', 'Asia/Hong_Kong', 'Asia/Taipei', 'Asia/Tokyo', 'Asia/Seoul', 'UTC', 'America/New_York', 'Europe/London'];
        var tzSelect = '<div class="form-group"><label>时区</label><select id="app-timezone">';
        tzOpts.forEach(function(tz) {
            tzSelect += '<option value="' + tz + '"' + (tz === adv.timezone ? ' selected' : '') + '>' + (tz || '自动') + '</option>';
        });
        tzSelect += '</select></div>';

        var kbOpts = [
            { v: '', l: '自动' },
            { v: 'en-us-qwerty', l: 'English (US)' },
            { v: 'ja-jp-qwerty', l: '日本語' },
            { v: 'de-de-qwertz', l: 'Deutsch' },
            { v: 'fr-fr-azerty', l: 'Français' },
            { v: 'zh-cn-qwerty', l: '中文' },
            { v: 'ko-kr', l: '한국어' },
        ];
        var kbSelect = '<div class="form-group"><label>键盘布局</label><select id="app-keyboard-layout">';
        kbOpts.forEach(function(o) {
            kbSelect += '<option value="' + o.v + '"' + (o.v === adv.keyboard_layout ? ' selected' : '') + '>' + o.l + '</option>';
        });
        kbSelect += '</select></div>';

        _pools.map(function(pool) {
            var selected = app && pool.id === app.pool_id ? ' selected' : '';
            return '<option value="' + pool.id + '"' + selected + '>' + escapeHtml(pool.name) + '</option>';
        }).join('');
        var defaultPoolId = app && app.pool_id ? app.pool_id : _pools[0].id;
        var appKindSelect = '<div class="form-group"><label>应用分类</label><select id="app-kind">' +
            buildAppKindOptions(app && app.app_kind ? app.app_kind : 'commercial_software') +
            '</select></div>';
        var poolSelect = '<div class="form-group"><label>资源池</label><select id="app-pool-id">' +
            _pools.map(function(pool) {
                var selected = pool.id === defaultPoolId ? ' selected' : '';
                return '<option value="' + pool.id + '"' + selected + '>' + escapeHtml(pool.name) + '</option>';
            }).join('') + '</select></div>';

        var scriptWorkerGroupId = app && app.script_worker_group_id ? String(app.script_worker_group_id) : '';
        var scriptProfileKey = app && app.script_profile_key ? String(app.script_profile_key) : '';
        var workerGroupSelect = '<div class="form-group"><label>脚本 Worker 组</label><select id="app-script-worker-group">' +
            '<option value="">未选择</option>' +
            _workerGroups.map(function(group) {
                var selected = String(group.id) === scriptWorkerGroupId ? ' selected' : '';
                return '<option value="' + group.id + '"' + selected + '>' + escapeHtml(group.name) + '</option>';
            }).join('') +
            '</select></div>';
        var scriptProfileSelect = '<div class="form-group"><label>软件预设</label><select id="app-script-profile-key">' +
            '<option value="">未选择</option>' +
            _scriptProfiles.map(function(profile) {
                var selected = profile.profile_key === scriptProfileKey ? ' selected' : '';
                return '<option value="' + escapeAttr(profile.profile_key) + '"' + selected + '>' + escapeHtml(profile.display_name) + '</option>';
            }).join('') +
            '</select></div>';
        var scriptExecutorSelect = '<div class="form-group"><label>脚本执行器</label><select id="app-script-executor">' +
            '<option value="">未选择</option>' +
            '<option value="python_api"' + ((app && app.script_executor_key === 'python_api') ? ' selected' : '') + '>python_api</option>' +
            '<option value="command_statusfile"' + ((app && app.script_executor_key === 'command_statusfile') ? ' selected' : '') + '>command_statusfile</option>' +
            '</select></div>';
        var scriptHtml =
            '<details class="advanced-params">' +
            '<summary>脚本模式</summary>' +
            '<div class="advanced-params__body">' +
            '<div class="info-callout" style="margin-bottom:0.8rem;">' +
            '<div class="info-callout__title">脚本模式怎么填</div>' +
            '<ul class="info-callout__list">' +
            '<li><strong>软件预设</strong>：告诉系统需要什么软件环境。</li>' +
            '<li><strong>执行器</strong>：告诉 Worker 用哪种方式拉起脚本。</li>' +
            '<li><strong>Worker 组</strong>：告诉系统要把任务派到哪一类机器。</li>' +
            '</ul></div>' +
            _chk('启用脚本模式', 'app-script-enabled', !!(app && app.script_enabled)) +
            '<div class="form-row">' + scriptProfileSelect + scriptExecutorSelect + workerGroupSelect + '</div>' +
            '<div class="form-group"><label>预设说明</label><div id="app-script-profile-desc" class="script-profile-desc"></div></div>' +
            formGroup('脚本 scratch 根目录', 'app-script-scratch-root', app ? (app.script_scratch_root || '') : '', 'text', false, '留空使用节点默认') +
            '<div class="field-hint">只在某个应用需要覆盖节点默认 scratch 时填写；大多数情况留空更安全。</div>' +
            formGroup('Python 解释器路径', 'app-script-python-executable', app ? (app.script_python_executable || '') : '', 'text', false, '留空使用 Worker 默认 Python') +
            '<div class="field-hint">只有这类应用必须绑定特定 Python 时再填。乱填只会把任务送进坑里。</div>' +
            formGroup('额外环境 JSON', 'app-script-python-env', app && app.script_python_env ? JSON.stringify(app.script_python_env) : '', 'text', false, '如 {\"LICENSE_SERVER\":\"1.2.3.4\"}') +
            '<div class="field-hint">这里只放脚本运行时必须的环境变量。写成 JSON，对象键值都用字符串。</div>' +
            '<div class="preview-box" id="app-script-summary"></div>' +
            '</div></details>';

        var advancedHtml =
            '<details class="advanced-params">' +
            '<summary>高级 RDP 参数</summary>' +
            '<div class="advanced-params__body">' +
            '<div class="advanced-params__section">' +
            '<div class="advanced-params__section-title">显示与性能</div>' +
            '<div class="form-row">' +
            depthSelect +
            formGroupSelect('缩放模式', 'app-resize-method', ['display-update', 'reconnect'], adv.resize_method) +
            '</div>' +
            _chk('禁用 GFX Pipeline (推荐)', 'app-disable-gfx', adv.disable_gfx) +
            _chk('显示桌面壁纸', 'app-enable-wallpaper', adv.enable_wallpaper) +
            _chk('字体平滑 (ClearType)', 'app-enable-font-smoothing', adv.enable_font_smoothing) +
            '</div>' +
            '<div class="advanced-params__section">' +
            '<div class="advanced-params__section-title">安全与剪贴板</div>' +
            _chk('禁止远程→本地复制', 'app-disable-copy', adv.disable_copy) +
            _chk('禁止本地→远程粘贴', 'app-disable-paste', adv.disable_paste) +
            '</div>' +
            '<div class="advanced-params__section">' +
            '<div class="advanced-params__section-title">文件传输通道</div>' +
            '<div class="form-row">' +
            '<div class="form-group"><label for="app-disable-download">浏览器下载通道</label><select id="app-disable-download">' +
            buildTriStatePolicyOptions(app ? app.disable_download : null) +
            '</select></div>' +
            '<div class="form-group"><label for="app-disable-upload">浏览器上传通道</label><select id="app-disable-upload">' +
            buildTriStatePolicyOptions(app ? app.disable_upload : null) +
            '</select></div>' +
            '</div>' +
            '<div class="field-hint">继承全局=跟随系统配置；强制允许会覆盖全局禁用。</div>' +
            '</div>' +
            '<div class="advanced-params__section">' +
            '<div class="advanced-params__section-title">音频与设备</div>' +
            _chk('音频输出', 'app-enable-audio', adv.enable_audio) +
            _chk('麦克风输入', 'app-enable-audio-input', adv.enable_audio_input) +
            _chk('虚拟打印机 (PDF)', 'app-enable-printing', adv.enable_printing) +
            '</div>' +
            '<div class="advanced-params__section">' +
            '<div class="advanced-params__section-title">本地化</div>' +
            '<div class="form-row">' +
            tzSelect + kbSelect +
            '</div></div>' +
            '</div></details>';
        var attachmentLineHint = '每行一条：标题 | 摘要 | https://链接。摘要可留空。';
        var poolAttachmentHtml = isEdit ? (
            '<details class="advanced-params">' +
            '<summary>资源池共享附件</summary>' +
            '<div class="advanced-params__body">' +
            '<div class="info-callout" style="margin-bottom:0.8rem;">' +
            '<div class="info-callout__title">这不是单个 App 私货</div>' +
            '<div class="field-hint">这里维护的是当前资源池共享附件。切池子就切到另一套内容，别脑补成 App 私有附件。</div>' +
            '</div>' +
            '<input type="hidden" id="pool-attachment-bound-pool-id" value="' + escapeAttr(defaultPoolId) + '">' +
            '<div id="pool-attachment-status" class="field-hint">正在准备共享附件编辑器...</div>' +
            '<div class="form-group"><label for="pool-attachment-tutorial-docs">教程文档</label>' +
            '<textarea id="pool-attachment-tutorial-docs" rows="4" placeholder="' + escapeAttr(attachmentLineHint) + '"></textarea></div>' +
            '<div class="form-group"><label for="pool-attachment-video-resources">视频资源</label>' +
            '<textarea id="pool-attachment-video-resources" rows="4" placeholder="' + escapeAttr(attachmentLineHint) + '"></textarea></div>' +
            '<div class="form-group"><label for="pool-attachment-plugin-downloads">插件下载</label>' +
            '<textarea id="pool-attachment-plugin-downloads" rows="4" placeholder="' + escapeAttr(attachmentLineHint) + '"></textarea></div>' +
            '<div class="field-hint">最简写法：标题 | 链接。需要摘要时再加中间那段。</div>' +
            '<div class="modal__actions">' +
            '<button type="button" class="btn btn--outline" id="pool-attachment-clear-btn">清空池附件</button>' +
            '<button type="button" class="btn btn--primary" id="pool-attachment-save-btn">保存池附件</button>' +
            '</div>' +
            '</div></details>'
        ) : '';

        var html = '<div class="modal-overlay" onclick="closeModal(event)">' +
            '<div class="modal" onclick="event.stopPropagation()">' +
            '<div class="modal__title">' + escapeHtml(title) + '</div>' +
            '<form id="app-form">' +
            '<div class="form-row">' +
            formGroup('名称', 'app-name', app ? app.name : '', 'text', true) +
            formGroup('图标', 'app-icon', app ? app.icon : 'desktop') +
            '</div>' +
            '<div class="form-row">' +
            formGroup('主机', 'app-hostname', app ? app.hostname : '', 'text', true) +
            formGroup('端口', 'app-port', app ? app.port : 3389, 'number') +
            '</div>' +
            '<div class="form-row">' +
            formGroup('RDP 用户名', 'app-rdp-user', app ? (app.rdp_username || '') : '') +
            formGroup('RDP 密码', 'app-rdp-pass', app ? (app.rdp_password || '') : '', 'password') +
            '</div>' +
            '<div class="form-row">' +
            formGroup('域名', 'app-domain', app ? (app.domain || '') : '') +
            formGroupSelect('安全模式', 'app-security', ['nla', 'tls', 'rdp', 'any'], app ? (app.security || 'nla') : 'nla') +
            '</div>' +
            formGroup('RemoteApp', 'app-remote-app', app ? (app.remote_app || '') : '', 'text', false, '如 ||notepad') +
            '<div class="form-row">' +
            appKindSelect +
            poolSelect +
            '</div>' +
            '<div class="field-hint">应用分类决定它在门户里落到哪个栏目。别乱选，分类和资源池用途打架时后端会直接拒绝。</div>' +
            '<div class="form-row">' +
            formGroup('成员并发上限', 'app-member-max', app ? (app.member_max_concurrent || 1) : 1, 'number', true) +
            '</div>' +
            '<div class="form-row">' +
            formGroup('工作目录', 'app-remote-dir', app ? (app.remote_app_dir || '') : '') +
            formGroup('命令参数', 'app-remote-args', app ? (app.remote_app_args || '') : '') +
            '</div>' +
            '<div class="form-group form-group--checkbox">' +
            '<input type="checkbox" id="app-ignore-cert"' + ((!app || app.ignore_cert) ? ' checked' : '') + '>' +
            '<label for="app-ignore-cert">忽略证书错误</label>' +
            '</div>' +
            poolAttachmentHtml +
            scriptHtml +
            advancedHtml +
            (isEdit ? '<div class="form-group form-group--checkbox">' +
                '<input type="checkbox" id="app-is-active"' + (app.is_active ? ' checked' : '') + '>' +
                '<label for="app-is-active">启用</label></div>' : '') +
            '<div class="modal__actions">' +
            '<button type="button" class="btn btn--outline" onclick="closeModal()">取消</button>' +
            '<button type="submit" class="btn btn--primary">' + (isEdit ? '保存' : '创建') + '</button>' +
            '</div>' +
            '</form></div></div>';

        document.getElementById('modal-container').innerHTML = html;
        document.getElementById('app-form').onsubmit = function(e) {
            e.preventDefault();
            saveApp(isEdit ? app.id : null);
        };
        var profileSelectEl = document.getElementById('app-script-profile-key');
        if (profileSelectEl) {
            profileSelectEl.addEventListener('change', applySelectedScriptProfile);
            updateScriptProfileHint(profileSelectEl.value);
        }
        var poolSelectEl = document.getElementById('app-pool-id');
        if (poolSelectEl && isEdit) {
            poolSelectEl.addEventListener('change', function() {
                refreshPoolAttachmentBindingStatus();
            });
        }
        var poolAttachmentSaveBtn = document.getElementById('pool-attachment-save-btn');
        if (poolAttachmentSaveBtn) {
            poolAttachmentSaveBtn.addEventListener('click', function() {
                savePoolAttachments();
            });
        }
        var poolAttachmentClearBtn = document.getElementById('pool-attachment-clear-btn');
        if (poolAttachmentClearBtn) {
            poolAttachmentClearBtn.addEventListener('click', function() {
                clearPoolAttachments();
            });
        }
        ['app-script-enabled', 'app-script-profile-key', 'app-script-executor', 'app-script-worker-group'].forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.addEventListener('change', updateScriptBindingSummary);
        });
        updateScriptBindingSummary();
        if (isEdit) {
            await loadPoolAttachmentEditors(defaultPoolId);
            refreshPoolAttachmentBindingStatus();
        }
    }

    function updateScriptBindingSummary() {
        var summaryEl = document.getElementById('app-script-summary');
        if (!summaryEl) return;
        var groupId = document.getElementById('app-script-worker-group');
        var profileKey = document.getElementById('app-script-profile-key');
        var executorKey = document.getElementById('app-script-executor');
        var enabledEl = document.getElementById('app-script-enabled');
        var group = _workerGroups.find(function(item) { return String(item.id) === String(groupId && groupId.value || ''); }) || null;
        var profile = findScriptProfile(profileKey ? profileKey.value : '');
        summaryEl.textContent = buildScriptBindingSummary({
            script_enabled: !!(enabledEl && enabledEl.checked),
            executor_key: executorKey ? executorKey.value : '',
            worker_group_name: group ? group.name : '',
            profile_name: profile ? profile.display_name : '',
        });
    }

    async function saveApp(appId) {
        var depthVal = document.getElementById('app-color-depth').value;
        var data = {
            name: document.getElementById('app-name').value.trim(),
            icon: document.getElementById('app-icon').value.trim() || 'desktop',
            app_kind: document.getElementById('app-kind').value || 'commercial_software',
            hostname: document.getElementById('app-hostname').value.trim(),
            port: parseInt(document.getElementById('app-port').value) || 3389,
            rdp_username: document.getElementById('app-rdp-user').value.trim(),
            rdp_password: document.getElementById('app-rdp-pass').value.trim(),
            domain: document.getElementById('app-domain').value.trim(),
            security: document.getElementById('app-security').value,
            ignore_cert: document.getElementById('app-ignore-cert').checked,
            remote_app: document.getElementById('app-remote-app').value.trim(),
            remote_app_dir: document.getElementById('app-remote-dir').value.trim(),
            remote_app_args: document.getElementById('app-remote-args').value.trim(),
            color_depth: depthVal ? parseInt(depthVal) : null,
            disable_gfx: document.getElementById('app-disable-gfx').checked,
            resize_method: document.getElementById('app-resize-method').value,
            enable_wallpaper: document.getElementById('app-enable-wallpaper').checked,
            enable_font_smoothing: document.getElementById('app-enable-font-smoothing').checked,
            disable_copy: document.getElementById('app-disable-copy').checked,
            disable_paste: document.getElementById('app-disable-paste').checked,
            enable_audio: document.getElementById('app-enable-audio').checked,
            enable_audio_input: document.getElementById('app-enable-audio-input').checked,
            enable_printing: document.getElementById('app-enable-printing').checked,
            disable_download: parseTriStatePolicy(document.getElementById('app-disable-download').value),
            disable_upload: parseTriStatePolicy(document.getElementById('app-disable-upload').value),
            timezone: document.getElementById('app-timezone').value || null,
            keyboard_layout: document.getElementById('app-keyboard-layout').value || null,
            pool_id: document.getElementById('app-pool-id').value ? parseInt(document.getElementById('app-pool-id').value, 10) : null,
            member_max_concurrent: parseInt(document.getElementById('app-member-max').value, 10) || 1,
            script_enabled: document.getElementById('app-script-enabled').checked,
            script_profile_key: document.getElementById('app-script-profile-key').value || null,
            script_executor_key: document.getElementById('app-script-executor').value || null,
            script_worker_group_id: document.getElementById('app-script-worker-group').value ? parseInt(document.getElementById('app-script-worker-group').value, 10) : null,
            script_scratch_root: document.getElementById('app-script-scratch-root').value.trim() || null,
            script_python_executable: document.getElementById('app-script-python-executable').value.trim() || null,
            script_python_env: null,
        };

        if (!data.name || !data.hostname) {
            showToast('名称和主机为必填项', 'error');
            return;
        }
        if (!data.pool_id) {
            showToast('请选择资源池', 'error');
            return;
        }
        if (data.script_enabled && (!data.script_executor_key || !data.script_worker_group_id)) {
            showToast('启用脚本模式时必须选择执行器和 Worker 组', 'error');
            return;
        }
        if (data.script_executor_key === 'python_api') {
            var envText = document.getElementById('app-script-python-env').value.trim();
            if (envText) {
                try {
                    data.script_python_env = JSON.parse(envText);
                } catch (e) {
                    showToast('额外环境 JSON 格式不合法', 'error');
                    return;
                }
            }
        }

        var isActiveEl = document.getElementById('app-is-active');
        if (isActiveEl) data.is_active = isActiveEl.checked;

        try {
            if (appId) {
                await api('PUT', '/apps/' + appId, data);
                showToast('应用已更新');
            } else {
                await api('POST', '/apps', data);
                showToast('应用已创建');
            }
            closeModal();
            loadApps();
        } catch (e) { showToast(e.message, 'error'); }
    }

    root.AdminAppUi = {
        loadApps: loadApps,
        renderAppsTable: renderAppsTable,
        deleteApp: deleteApp,
        normalizeTriStatePolicy: normalizeTriStatePolicy,
        buildTriStatePolicyOptions: buildTriStatePolicyOptions,
        parseTriStatePolicy: parseTriStatePolicy,
        ensureWorkerGroupsLoaded: ensureWorkerGroupsLoaded,
        ensureScriptProfilesLoaded: ensureScriptProfilesLoaded,
        findScriptProfile: findScriptProfile,
        updateScriptProfileHint: updateScriptProfileHint,
        applySelectedScriptProfile: applySelectedScriptProfile,
        showAppModal: showAppModal,
        updateScriptBindingSummary: updateScriptBindingSummary,
        saveApp: saveApp,
        loadPoolAttachmentEditors: loadPoolAttachmentEditors,
        savePoolAttachments: savePoolAttachments,
        clearPoolAttachments: clearPoolAttachments,
    };
})(typeof window !== 'undefined' ? window : globalThis);
