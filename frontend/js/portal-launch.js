// ---- 防重复点击锁 ----
var _launchLock = {};
var _queueTickets = {};
var _queuePollers = {};

async function launchApp(appId, appName, poolId) {
    await _launchWithWindow(appId, appName, poolId, null, false);
}

function _openLaunchWindow() {
    return window.open('about:blank', '_blank');
}

function _renderLoadingWindow(win, title, text) {
    if (!win || win.closed) return;
    win.document.open();
    win.document.write(
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">' +
        '<title>' + title + '</title>' +
        '<style>*{margin:0;padding:0}body{display:flex;align-items:center;justify-content:center;height:100vh;font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",\"Microsoft YaHei\",sans-serif;background:#1a1a2e;color:#fff}.spinner{width:40px;height:40px;margin:0 auto 1rem;border:4px solid rgba(255,255,255,0.2);border-top-color:#fff;border-radius:50%;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}</style></head><body>' +
        '<div style="text-align:center"><div class="spinner"></div><p>' + text + '</p></div>' +
        '</body></html>'
    );
    win.document.close();
}

function _renderQueueWindow(win, appName, status, position) {
    if (!win || win.closed) return;
    var safeName = escapeHtml(appName);
    var message = '正在排队...';
    if (status === 'ready') message = '轮到你了，正在尝试启动...';
    else if (status === 'launching') message = '正在占用资源并启动...';

    win.document.open();
    win.document.write(
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">' +
        '<title>' + safeName + ' - 排队中</title>' +
        '<style>*{margin:0;padding:0;box-sizing:border-box}body{display:flex;align-items:center;justify-content:center;height:100vh;font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",\"Microsoft YaHei\",sans-serif;background:linear-gradient(135deg,#1f2a44,#314c7a);color:#fff;padding:1.5rem}.box{max-width:420px;background:rgba(255,255,255,.08);padding:1.5rem;border-radius:18px;text-align:center;backdrop-filter:blur(10px)}.pill{display:inline-block;background:rgba(255,255,255,.14);padding:.2rem .7rem;border-radius:999px;font-size:.8rem;margin-bottom:.9rem}.desc{font-size:.92rem;color:rgba(255,255,255,.84);margin-top:.5rem}</style></head><body>' +
        '<div class="box"><div class="pill">资源池排队</div><h1 style="font-size:1.15rem">' + safeName + '</h1><p style="margin-top:.9rem;font-size:1rem">' + escapeHtml(message) + '</p><p class="desc">当前位置: ' + (position > 0 ? ('#' + position) : '-') + '</p><p class="desc">保持此窗口开启，轮到时会自动继续。</p></div>' +
        '</body></html>'
    );
    win.document.close();
}

function _renderGuacWindow(win, appName, data) {
    if (!win) {
        showError('弹窗被浏览器拦截，请允许本站弹出窗口');
        return;
    }
    var safeName = escapeHtml(appName);

    win.document.open();
    win.document.write(
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>' + safeName + '</title><style>html,body{margin:0;padding:0;overflow:hidden}</style></head><body>' +
        '<iframe id="guac" src="' + escapeHtml(data.redirect_url) + '" style="width:100vw;height:100vh;border:none" allow="clipboard-read;clipboard-write" onload="this.focus()"></iframe>' +
        '<script>' +
        'var f=document.getElementById(\"guac\");' +
        'document.body.addEventListener(\"click\",function(){f.focus()});' +
        'document.addEventListener(\"keydown\",function(e){if(document.activeElement!==f){e.preventDefault();f.focus();}},true);' +
        'var wb=new Blob([\"setInterval(function(){postMessage(1)},30000)\"],{type:\"text/javascript\"});' +
        'var wk=new Worker(URL.createObjectURL(wb));' +
        'wk.onmessage=function(){try{f.contentWindow.postMessage(\"keepalive\",\"*\")}catch(e){}};' +
        'var _sid=\"' + (data.session_id || '') + '\";' +
        'var _token=\"' + getToken() + '\";' +
        'if(_sid){' +
        '  var _hbUrl=\"/api/monitor/heartbeat\";' +
        '  var _activityUrl=\"/api/monitor/activity\";' +
        '  var _endUrl=\"/api/monitor/session-end\";' +
        '  var _defaultReclaimMessage=\"该会话已被系统回收，窗口将关闭\";' +
        '  var _control=null;' +
        '  var _hbTimer=0;' +
        '  var _activityTimer=0;' +
        '  var _activityHandler=null;' +
        '  var _notifySessionEnd=function(){' +
        '    try{navigator.sendBeacon(_endUrl,new Blob([JSON.stringify({session_id:_sid})],{type:\"application/json\"}))}catch(e){}' +
        '  };' +
        '  var _closePopupWithNotice=function(message){' +
        '    if(window.__portalReclaimClosing){return;}' +
        '    window.__portalReclaimClosing=true;' +
        '    var _text=(typeof message===\"string\"&&message)?message:_defaultReclaimMessage;' +
        '    _notifySessionEnd();' +
        '    try{' +
        '      var _notice=document.createElement(\"div\");' +
        '      _notice.setAttribute(\"style\",\"position:fixed;top:0;left:0;right:0;z-index:2147483647;padding:10px 14px;background:#b91c1c;color:#fff;font:14px/1.4 -apple-system,BlinkMacSystemFont,\\\"Segoe UI\\\",\\\"Microsoft YaHei\\\",sans-serif;text-align:center\");' +
        '      _notice.textContent=_text;' +
        '      document.body.appendChild(_notice);' +
        '    }catch(e){}' +
        '    setTimeout(function(){window.close();},1500);' +
        '  };' +
        '  var _createFallbackControl=function(){' +
        '    var _stopped=false;' +
        '    var _handled=false;' +
        '    return {' +
        '      shouldReport:function(){return !_stopped;},' +
        '      processNetworkError:function(){return {reclaimed:false,message:\"\"};},' +
        '      processResponse:function(status,payload){' +
        '        if(_stopped){return {reclaimed:true,message:_defaultReclaimMessage};}' +
        '        if(status===409&&payload&&(payload.code===\"session_reclaimed\"||payload.code===\"session_idle_reclaimed\")){' +
        '          _stopped=true;' +
        '          var _msg=(typeof payload.detail===\"string\"&&payload.detail)?payload.detail:_defaultReclaimMessage;' +
        '          if(!_handled){_handled=true;_closePopupWithNotice(_msg);}' +
        '          return {reclaimed:true,message:_msg};' +
        '        }' +
        '        return {reclaimed:false,message:\"\"};' +
        '      }' +
        '    };' +
        '  };' +
        '  var _stopReporting=function(){' +
        '    if(_hbTimer){clearInterval(_hbTimer);_hbTimer=0;}' +
        '    if(_activityTimer){clearInterval(_activityTimer);_activityTimer=0;}' +
        '    if(_activityHandler){' +
        '      window.removeEventListener(\"focus\",_activityHandler);' +
        '      document.removeEventListener(\"click\",_activityHandler,true);' +
        '      document.removeEventListener(\"keydown\",_activityHandler,true);' +
        '      _activityHandler=null;' +
        '    }' +
        '  };' +
        '  var _postMonitor=function(url){' +
        '    if(!_control||!_control.shouldReport()){return;}' +
        '    fetch(url,{method:\"POST\",headers:{\"Authorization\":\"Bearer \"+_token,\"Content-Type\":\"application/json\"},body:JSON.stringify({session_id:_sid})})' +
        '      .then(function(resp){' +
        '        if(!_control||!_control.shouldReport()||resp.ok){return;}' +
        '        return resp.json().catch(function(){return null;}).then(function(payload){' +
        '          var decision=_control.processResponse(resp.status,payload);' +
        '          if(decision&&decision.reclaimed){_stopReporting();}' +
        '        });' +
        '      })' +
        '      .catch(function(err){if(_control){_control.processNetworkError(err);}});' +
        '  };' +
        '  var _startReporting=function(){' +
        '    _hbTimer=setInterval(function(){_postMonitor(_hbUrl);},30000);' +
        '    _activityHandler=function(){_postMonitor(_activityUrl);};' +
        '    _activityTimer=setInterval(function(){if(_control&&_control.shouldReport()&&document.activeElement===f&&document.hasFocus()){_activityHandler();}},15000);' +
        '    window.addEventListener(\"focus\",_activityHandler);' +
        '    document.addEventListener(\"click\",_activityHandler,true);' +
        '    document.addEventListener(\"keydown\",_activityHandler,true);' +
        '  };' +
        '  import(\"/js/portal-session-control.js\")' +
        '    .then(function(mod){_control=mod.createPortalSessionControl({onReclaimed:_closePopupWithNotice});_startReporting();})' +
        '    .catch(function(){_control=_createFallbackControl();_startReporting();});' +
        '  window.addEventListener(\"beforeunload\",function(){if(_control&&!_control.shouldReport()){return;}_notifySessionEnd();});' +
        '}' +
        '</script></body></html>'
    );
    win.document.close();
}

function _upsertQueueTicket(ticket) {
    _queueTickets[ticket.queueId] = Object.assign(_queueTickets[ticket.queueId] || {}, ticket);
    renderQueueTickets();
}

function _removeQueueTicket(queueId) {
    if (_queuePollers[queueId]) {
        clearInterval(_queuePollers[queueId]);
        delete _queuePollers[queueId];
    }
    delete _queueTickets[queueId];
    renderQueueTickets();
}

function renderQueueTickets() {
    var container = document.getElementById('queue-status');
    if (!container) return;
    var ids = Object.keys(_queueTickets);
    if (!ids.length) {
        container.style.display = 'none';
        container.innerHTML = '';
        return;
    }

    container.style.display = '';
    container.innerHTML = ids.map(function(id) {
        var ticket = _queueTickets[id];
        var label = '排队中';
        if (ticket.status === 'ready') label = '已就绪';
        else if (ticket.status === 'launching') label = '正在启动';
        return '<div class="queue-ticket"><div class="queue-ticket__row"><div><div class="queue-ticket__title">' + escapeHtml(ticket.appName) + ' · ' + label + '</div><div class="queue-ticket__meta">队列编号 #' + ticket.queueId + ' · 当前位置 ' + (ticket.position > 0 ? ('#' + ticket.position) : '-') + '</div></div><div class="queue-ticket__actions">' +
            (ticket.status === 'ready' ? '<button class="queue-ticket__btn queue-ticket__btn--primary" onclick="resumeQueuedLaunch(' + ticket.queueId + ')">立即启动</button>' : '') +
            '<button class="queue-ticket__btn queue-ticket__btn--ghost" onclick="cancelQueuedLaunch(' + ticket.queueId + ')">取消</button></div></div></div>';
    }).join('');
}

async function cancelQueuedLaunch(queueId) {
    try {
        var resp = await fetch(API_BASE + '/queue/' + queueId, {
            method: 'DELETE',
            headers: authHeaders(),
        });
        if (resp.status === 401) { logout(); return; }
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return {}; });
            showError(err.detail || '取消排队失败');
            return;
        }
        var ticket = _queueTickets[queueId];
        if (ticket && ticket.win && !ticket.win.closed) {
            ticket.win.close();
        }
        _removeQueueTicket(queueId);
    } catch (e) {
        showError('取消排队失败: ' + (e.message || ''));
    }
}

async function resumeQueuedLaunch(queueId) {
    var ticket = _queueTickets[queueId];
    if (!ticket) return;
    var win = ticket.win;
    if (!win || win.closed) {
        win = _openLaunchWindow();
        ticket.win = win;
    }
    if (!win) {
        showError('弹窗被浏览器拦截，请允许本站弹出窗口');
        return;
    }
    await _launchWithWindow(ticket.appId, ticket.appName, ticket.poolId, queueId, true);
}

function _startQueuePolling(queueId) {
    if (_queuePollers[queueId]) return;
    _queuePollers[queueId] = setInterval(function() {
        _pollQueueStatus(queueId);
    }, 5000);
}

async function _pollQueueStatus(queueId) {
    var ticket = _queueTickets[queueId];
    if (!ticket) return;
    try {
        var resp = await fetch(API_BASE + '/queue/' + queueId, { headers: authHeaders() });
        if (resp.status === 401) { logout(); return; }
        if (resp.status === 404) {
            _removeQueueTicket(queueId);
            return;
        }
        if (!resp.ok) return;
        var data = await resp.json();
        ticket.status = data.status;
        ticket.position = data.position || 0;
        if (ticket.status === 'cancelled' || ticket.status === 'expired' || ticket.status === 'fulfilled') {
            if (ticket.win && !ticket.win.closed) ticket.win.close();
            _removeQueueTicket(queueId);
            return;
        }
        _upsertQueueTicket(ticket);
        if (ticket.win && !ticket.win.closed) {
            _renderQueueWindow(ticket.win, ticket.appName, ticket.status, ticket.position);
        }
        if (ticket.status === 'ready' && ticket.win && !ticket.win.closed) {
            await resumeQueuedLaunch(queueId);
        }
    } catch (e) {}
}

async function _launchWithWindow(appId, appName, poolId, queueId, skipLock) {
    if (!skipLock) {
        if (_launchLock[appId] && Date.now() - _launchLock[appId] < 3000) return;
        _launchLock[appId] = Date.now();
    }

    var win = queueId ? (_queueTickets[queueId] && _queueTickets[queueId].win) : null;
    if (!win || win.closed) {
        win = _openLaunchWindow();
    }
    if (!win) {
        showError('弹窗被浏览器拦截，请允许本站弹出窗口');
        if (!skipLock) delete _launchLock[appId];
        return;
    }

    var safeName = escapeHtml(appName);
    _renderLoadingWindow(win, safeName + ' - 加载中...', queueId ? ('正在接入 ' + safeName + ' ...') : ('正在启动 ' + safeName + '...'));

    try {
        var headers = authHeaders();
        var body = null;
        if (queueId) {
            headers = {
                'Authorization': headers.Authorization,
                'Content-Type': 'application/json',
            };
            body = JSON.stringify({ queue_id: queueId });
        }
        var resp = await fetch(API_BASE + '/launch/' + appId, {
            method: 'POST',
            headers: headers,
            body: body,
        });
        if (resp.status === 401) { win.close(); logout(); return; }
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return {}; });
            throw new Error(err.detail || 'HTTP ' + resp.status);
        }
        var data = await resp.json();
        if (data.status === 'queued' || data.status === 'ready' || data.status === 'launching') {
            _upsertQueueTicket({
                queueId: data.queue_id,
                appId: appId,
                appName: appName,
                poolId: data.pool_id || poolId || 0,
                position: data.position || 0,
                status: data.status,
                win: win,
            });
            _renderQueueWindow(win, appName, data.status, data.position || 0);
            _startQueuePolling(data.queue_id);
            return;
        }
        if (queueId) {
            _removeQueueTicket(queueId);
        } else if (data.queue_id) {
            _removeQueueTicket(data.queue_id);
        }
        _renderGuacWindow(win, appName, data);
    } catch (e) {
        var safeMsg = escapeHtml(e.message || '未知错误');
        win.document.open();
        win.document.write(
            '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>\u542F\u52A8\u5931\u8D25</title><style>*{margin:0;padding:0}body{display:flex;align-items:center;justify-content:center;height:100vh;font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",\"Microsoft YaHei\",sans-serif;background:#1a1a2e;color:#e74c3c}</style></head><body><div style="text-align:center"><p style="font-size:1.2rem">\u542F\u52A8\u5931\u8D25</p><p style="margin-top:.5rem;color:#aaa">' + safeMsg + '</p></div></body></html>'
        );
        win.document.close();
    } finally {
        if (!skipLock) {
            delete _launchLock[appId];
        }
    }
}

function renderCards(apps) {
    var grid = document.getElementById('app-grid');
    grid.innerHTML = '';

    apps.forEach(function(app) {
        var card = document.createElement('div');
        card.className = 'app-card' + ((!app.has_capacity || app.queued_count > 0) ? ' app-card--busy' : '');
        card.onclick = function() { launchApp(app.id, app.name, app.pool_id || 0); };

        var icon = ICON_MAP[app.icon] || ICON_MAP['desktop'];
        var appLabel = '资源池';

        var iconSpan = document.createElement('span');
        iconSpan.className = 'app-card__icon';
        iconSpan.textContent = icon;

        var nameDiv = document.createElement('div');
        nameDiv.className = 'app-card__name';
        nameDiv.textContent = app.name;

        var protoDiv = document.createElement('div');
        protoDiv.className = 'app-card__protocol';
        protoDiv.textContent = app.protocol.toUpperCase() + ' \u00B7 ' + appLabel;

        var statsDiv = document.createElement('div');
        statsDiv.className = 'app-card__stats';

        var activePill = document.createElement('span');
        activePill.className = 'app-card__pill';
        activePill.textContent = '运行 ' + (app.active_count || 0) + '/' + (app.max_concurrent || 1);

        var queuePill = document.createElement('span');
        queuePill.className = 'app-card__pill';
        queuePill.textContent = '排队 ' + (app.queued_count || 0);

        statsDiv.appendChild(activePill);
        statsDiv.appendChild(queuePill);

        card.appendChild(iconSpan);
        card.appendChild(nameDiv);
        card.appendChild(protoDiv);
        card.appendChild(statsDiv);
        grid.appendChild(card);
    });
}
