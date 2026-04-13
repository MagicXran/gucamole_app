var _uploads = {};
var CHUNK_SIZE = 10 * 1024 * 1024;
var _dragCounter = 0;

function triggerUpload() {
    document.getElementById('file-input').click();
}

function _handleFileSelect(evt) {
    var files = evt.target.files;
    for (var i = 0; i < files.length; i++) {
        uploadFile(files[i], _currentPath);
    }
    evt.target.value = '';
}

async function uploadFile(file, targetDir) {
    var path = (targetDir ? targetDir + '/' : '') + file.name;
    var id = Date.now() + '_' + Math.random().toString(36).slice(2, 8);

    _uploads[id] = {
        file: file, path: path, name: file.name,
        offset: 0, size: file.size, speed: 0,
        aborted: false, controller: new AbortController(),
        status: 'uploading', error: '',
    };

    renderUploads();

    try {
        var initForm = new FormData();
        initForm.append('path', path);
        initForm.append('size', file.size);

        var initResp = await fetch('/api/files/upload/init', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + getToken() },
            body: initForm,
            signal: _uploads[id].controller.signal,
        });
        if (initResp.status === 401) { logout(); return; }
        if (!initResp.ok) {
            var err = await initResp.json().catch(function() { return {}; });
            _uploads[id].status = 'error';
            _uploads[id].error = err.detail || 'init 失败';
            renderUploads();
            return;
        }
        var initData = await initResp.json();
        var uploadId = initData.upload_id;
        var offset = initData.offset || 0;

        _uploads[id].offset = offset;
        _uploads[id].uploadId = uploadId;
        renderUploads();

        var chunkTimes = [];
        while (offset < file.size) {
            if (_uploads[id].aborted) return;

            var end = Math.min(offset + CHUNK_SIZE, file.size);
            var blob = file.slice(offset, end);

            var chunkForm = new FormData();
            chunkForm.append('upload_id', uploadId);
            chunkForm.append('offset', offset);
            chunkForm.append('chunk', blob, file.name);

            var t0 = Date.now();
            var chunkResp = await fetch('/api/files/upload/chunk', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + getToken() },
                body: chunkForm,
                signal: _uploads[id].controller.signal,
            });

            if (!chunkResp.ok) {
                var cerr = await chunkResp.json().catch(function() { return {}; });
                _uploads[id].status = 'error';
                _uploads[id].error = cerr.detail || 'chunk 失败';
                renderUploads();
                return;
            }

            var chunkData = await chunkResp.json();
            var elapsed = (Date.now() - t0) / 1000;
            chunkTimes.push({ bytes: end - offset, time: elapsed });
            if (chunkTimes.length > 5) chunkTimes.shift();

            offset = chunkData.offset;
            _uploads[id].offset = offset;
            _uploads[id].speed = calcSpeed(chunkTimes);
            renderUploads();

            if (chunkData.complete) {
                _uploads[id].status = 'done';
                renderUploads();
                if (typeof markFilesRefreshBurst === 'function') {
                    markFilesRefreshBurst();
                }
                loadFiles(_currentPath);
                loadSpaceInfo();
                setTimeout(function(uid) { delete _uploads[uid]; renderUploads(); }, 3000, id);
                return;
            }
        }
    } catch (e) {
        if (!_uploads[id]) return;
        if (e.name === 'AbortError') {
            _uploads[id].status = 'cancelled';
        } else {
            _uploads[id].status = 'error';
            _uploads[id].error = e.message || '上传失败';
        }
        renderUploads();
    }
}

function cancelUpload(id) {
    var u = _uploads[id];
    if (!u) return;
    u.aborted = true;
    u.controller.abort();
    if (u.uploadId) {
        fetch('/api/files/upload/' + u.uploadId, {
            method: 'DELETE',
            headers: authHeaders(),
        }).catch(function() {});
    }
    delete _uploads[id];
    renderUploads();
}

function calcSpeed(chunkTimes) {
    if (!chunkTimes.length) return 0;
    var totalBytes = 0, totalTime = 0;
    chunkTimes.forEach(function(c) { totalBytes += c.bytes; totalTime += c.time; });
    return totalTime > 0 ? totalBytes / totalTime : 0;
}

function renderUploads() {
    var container = document.getElementById('files-uploads');
    if (!container) return;
    var keys = Object.keys(_uploads);
    if (!keys.length) { container.innerHTML = ''; return; }

    var html = '';
    keys.forEach(function(id) {
        var u = _uploads[id];
        var pct = u.size > 0 ? Math.round(u.offset / u.size * 100) : 0;
        var fillClass = 'files-upload-item__fill';
        if (u.status === 'done') fillClass += ' files-upload-item__fill--done';
        else if (u.status === 'error') fillClass += ' files-upload-item__fill--error';

        var statusText = '';
        if (u.status === 'done') statusText = '完成';
        else if (u.status === 'error') statusText = u.error;
        else if (u.status === 'cancelled') statusText = '已取消';
        else statusText = formatBytes(u.offset) + ' / ' + formatBytes(u.size);

        var speedText = u.status === 'uploading' && u.speed > 0 ? formatBytes(u.speed) + '/s' : '';

        html += '<div class="files-upload-item"><div class="files-upload-item__name"><span>' + escapeHtml(u.name) + '</span>' +
            (u.status === 'uploading' ? '<button class="files-upload-item__cancel" onclick="cancelUpload(\'' + id + '\')">取消</button>' : '') +
            '</div><div class="files-upload-item__progress"><div class="' + fillClass + '" style="width:' + pct + '%"></div></div>' +
            '<div class="files-upload-item__info"><span>' + statusText + '</span><span>' + speedText + '</span></div></div>';
    });
    container.innerHTML = html;
}

function _initDragDrop() {
    var body = document.body;
    body.addEventListener('dragenter', function(e) {
        if (_currentPortalTab !== 'files') return;
        e.preventDefault();
        _dragCounter++;
        document.getElementById('files-dropzone').classList.add('files-dropzone--active');
    });
    body.addEventListener('dragleave', function() {
        _dragCounter--;
        if (_dragCounter <= 0) {
            _dragCounter = 0;
            document.getElementById('files-dropzone').classList.remove('files-dropzone--active');
        }
    });
    body.addEventListener('dragover', function(e) {
        if (_currentPortalTab !== 'files') return;
        e.preventDefault();
    });
    body.addEventListener('drop', function(e) {
        e.preventDefault();
        _dragCounter = 0;
        document.getElementById('files-dropzone').classList.remove('files-dropzone--active');
        if (_currentPortalTab !== 'files') return;

        var files = e.dataTransfer.files;
        for (var i = 0; i < files.length; i++) {
            uploadFile(files[i], _currentPath);
        }
    });
}

function _initTip() {
    var hidden = localStorage.getItem('portal_files_tip_hidden') === '1';
    if (hidden) {
        var el = document.getElementById('files-tip');
        if (el) el.style.display = 'none';
    }
}

function closeTip() {
    var el = document.getElementById('files-tip');
    if (el) el.style.display = 'none';
    localStorage.setItem('portal_files_tip_hidden', '1');
}
