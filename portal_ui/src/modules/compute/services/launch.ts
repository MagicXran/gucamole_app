import { PORTAL_TOKEN_KEY } from '@/constants/auth'
import http from '@/services/http'

type LaunchResponse = {
  status: string
  redirect_url: string
  connection_name: string
  session_id: string
  queue_id: number
  position: number
  pool_id: number
}

type QueueStatusResponse = {
  queue_id: number
  pool_id: number
  status: string
  position: number
  ready_expires_at?: string | null
  cancel_reason?: string | null
}

type QueueTicket = {
  queueId: number
  appId: number
  appName: string
  poolId: number
  popup: Window
}

const launchLock = new Map<number, number>()
const queuePollers = new Map<number, number>()

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function getPopupOrThrow() {
  const popup = window.open('', '_blank')
  if (!popup) {
    throw new Error('弹窗被浏览器拦截，请允许本站弹出窗口')
  }
  return popup
}

function renderWindow(popup: Window, title: string, body: string) {
  popup.document.open()
  popup.document.write(
    '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">' +
      `<title>${escapeHtml(title)}</title>` +
      '<style>*{margin:0;padding:0;box-sizing:border-box}body{display:flex;align-items:center;justify-content:center;height:100vh;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;background:#0f172a;color:#fff;padding:1.5rem}.box{max-width:420px;background:rgba(255,255,255,.08);padding:1.5rem;border-radius:18px;text-align:center;backdrop-filter:blur(10px)}.spinner{width:40px;height:40px;margin:0 auto 1rem;border:4px solid rgba(255,255,255,0.2);border-top-color:#fff;border-radius:50%;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}.meta{margin-top:.8rem;font-size:.92rem;color:rgba(255,255,255,.76)}</style></head><body>' +
      `<div class="box">${body}</div>` +
      '</body></html>',
  )
  popup.document.close()
}

function renderLoadingWindow(popup: Window, appName: string, message: string) {
  renderWindow(
    popup,
    `${appName} - 启动中`,
    `<div class="spinner"></div><h1 style="font-size:1.15rem">${escapeHtml(appName)}</h1><p class="meta">${escapeHtml(message)}</p>`,
  )
}

function renderQueueWindow(popup: Window, appName: string, status: string, position: number) {
  let message = '正在排队...'
  if (status === 'ready') {
    message = '轮到你了，正在尝试启动...'
  } else if (status === 'launching') {
    message = '正在占用资源并启动...'
  }
  renderWindow(
    popup,
    `${appName} - 排队中`,
    `<h1 style="font-size:1.15rem">${escapeHtml(appName)}</h1><p class="meta">${escapeHtml(message)}</p><p class="meta">当前位置：${position > 0 ? `#${position}` : '-'}</p>`,
  )
}

function renderTerminalQueueWindow(popup: Window, appName: string, message: string) {
  renderWindow(
    popup,
    `${appName} - 队列结束`,
    `<h1 style="font-size:1.15rem">${escapeHtml(appName)}</h1><p class="meta">${escapeHtml(message)}</p>`,
  )
}

function renderErrorWindow(popup: Window, appName: string, message: string) {
  renderWindow(
    popup,
    `${appName} - 启动失败`,
    `<h1 style="font-size:1.15rem;color:#fca5a5">启动失败</h1><p class="meta">${escapeHtml(message)}</p>`,
  )
}

function stopQueuePolling(queueId: number) {
  const timer = queuePollers.get(queueId)
  if (timer) {
    window.clearInterval(timer)
    queuePollers.delete(queueId)
  }
}

function renderGuacamoleWindow(popup: Window, appName: string, redirectUrl: string, sessionId: string) {
  const token = localStorage.getItem(PORTAL_TOKEN_KEY) || ''
  const configJson = JSON.stringify({
    redirectUrl,
    sessionId,
    token,
    defaultReclaimMessage: '该会话已被系统回收，窗口将关闭',
  })

  popup.document.open()
  popup.document.write(
    '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">' +
      `<title>${escapeHtml(appName)}</title>` +
      '<style>html,body{margin:0;padding:0;overflow:hidden;background:#0f172a}iframe{width:100vw;height:100vh;border:none}</style></head><body>' +
      `<iframe id="guac-frame" src="${escapeHtml(redirectUrl)}" allow="clipboard-read;clipboard-write"></iframe>` +
      '<script>' +
      `const cfg=${configJson};` +
      'const frame=document.getElementById("guac-frame");' +
      'const notifySessionEnd=function(){try{navigator.sendBeacon("/api/monitor/session-end",new Blob([JSON.stringify({session_id:cfg.sessionId})],{type:"application/json"}))}catch(e){}};' +
      'const closePopupWithNotice=function(message){if(window.__portalClosing){return;}window.__portalClosing=true;try{const notice=document.createElement("div");notice.setAttribute("style","position:fixed;top:0;left:0;right:0;z-index:2147483647;padding:10px 14px;background:#b91c1c;color:#fff;font:14px/1.4 -apple-system,BlinkMacSystemFont,Segoe UI,Microsoft YaHei,sans-serif;text-align:center");notice.textContent=message||cfg.defaultReclaimMessage;document.body.appendChild(notice);}catch(e){}notifySessionEnd();setTimeout(function(){window.close();},1500);};' +
      'const fallbackControl={shouldReport:function(){return !window.__portalClosing;},processNetworkError:function(){return {reclaimed:false,message:""};},processResponse:function(status,payload){if(status===409&&payload&&(payload.code==="session_reclaimed"||payload.code==="session_idle_reclaimed")){closePopupWithNotice(typeof payload.detail==="string"&&payload.detail?payload.detail:cfg.defaultReclaimMessage);return {reclaimed:true,message:cfg.defaultReclaimMessage};}return {reclaimed:false,message:""};}};' +
      'let control=fallbackControl;' +
      'const postMonitor=function(url){if(!control.shouldReport()){return;}fetch(url,{method:"POST",headers:{"Authorization":"Bearer "+cfg.token,"Content-Type":"application/json"},body:JSON.stringify({session_id:cfg.sessionId})}).then(function(resp){if(!control.shouldReport()||resp.ok){return;}return resp.json().catch(function(){return null;}).then(function(payload){const decision=control.processResponse(resp.status,payload);if(decision&&decision.reclaimed){window.clearInterval(window.__portalHeartbeatTimer||0);window.clearInterval(window.__portalActivityTimer||0);}});}).catch(function(){control.processNetworkError();});};' +
      'window.__portalHeartbeatTimer=window.setInterval(function(){postMonitor("/api/monitor/heartbeat");},30000);' +
      'const activity=function(){postMonitor("/api/monitor/activity");};' +
      'window.__portalActivityTimer=window.setInterval(function(){if(document.hasFocus()){activity();}},15000);' +
      'window.addEventListener("focus",activity);' +
      'document.addEventListener("click",activity,true);' +
      'document.addEventListener("keydown",activity,true);' +
      'import("/js/portal-session-control.js").then(function(mod){control=mod.createPortalSessionControl({onReclaimed:closePopupWithNotice});}).catch(function(){});' +
      'window.addEventListener("beforeunload",function(){if(control.shouldReport()){notifySessionEnd();}});' +
      '</script></body></html>',
  )
  popup.document.close()
}

async function requestLaunch(appId: number, queueId?: number) {
  const response = await http.post<LaunchResponse>(`/api/remote-apps/launch/${appId}`, queueId ? { queue_id: queueId } : undefined)
  return response.data
}

async function requestQueueStatus(queueId: number) {
  const response = await http.get<QueueStatusResponse>(`/api/remote-apps/queue/${queueId}`)
  return response.data
}

function startQueuePolling(ticket: QueueTicket) {
  if (queuePollers.has(ticket.queueId)) {
    return
  }

  const timer = window.setInterval(async () => {
    try {
      const status = await requestQueueStatus(ticket.queueId)
      if (ticket.popup.closed) {
        stopQueuePolling(ticket.queueId)
        return
      }
      if (status.status === 'ready') {
        stopQueuePolling(ticket.queueId)
        await launchIntoPopup({
          appId: ticket.appId,
          appName: ticket.appName,
          poolId: ticket.poolId,
          popup: ticket.popup,
          queueId: ticket.queueId,
        })
        return
      }
      if (status.status === 'cancelled' || status.status === 'expired' || status.status === 'fulfilled') {
        stopQueuePolling(ticket.queueId)
        renderTerminalQueueWindow(ticket.popup, ticket.appName, status.cancel_reason || `排队状态：${status.status}`)
        return
      }
      renderQueueWindow(ticket.popup, ticket.appName, status.status, status.position)
    } catch (error) {
      stopQueuePolling(ticket.queueId)
      renderErrorWindow(
        ticket.popup,
        ticket.appName,
        error instanceof Error ? error.message : '排队状态查询失败',
      )
    }
  }, 5000)

  queuePollers.set(ticket.queueId, timer)
}

async function launchIntoPopup({
  appId,
  appName,
  poolId,
  popup,
  queueId,
}: {
  appId: number
  appName: string
  poolId: number
  popup: Window
  queueId?: number
}) {
  renderLoadingWindow(popup, appName, queueId ? '正在接入远程应用...' : '正在启动远程应用...')
  const payload = await requestLaunch(appId, queueId)
  if (payload.status === 'started' && payload.redirect_url) {
    if (payload.queue_id) {
      stopQueuePolling(payload.queue_id)
    }
    renderGuacamoleWindow(popup, appName, payload.redirect_url, payload.session_id)
    return
  }
  if (payload.queue_id) {
    renderQueueWindow(popup, appName, payload.status, payload.position)
    startQueuePolling({
      queueId: payload.queue_id,
      appId,
      appName,
      poolId: payload.pool_id || poolId,
      popup,
    })
    return
  }
  throw new Error(`未知启动状态：${payload.status}`)
}

export async function launchRemoteApp(appId: number, appName: string, poolId: number) {
  const previousLaunchAt = launchLock.get(appId) || 0
  if (Date.now() - previousLaunchAt < 3000) {
    return
  }
  launchLock.set(appId, Date.now())

  const popup = getPopupOrThrow()
  try {
    await launchIntoPopup({ appId, appName, poolId, popup })
  } catch (error) {
    renderErrorWindow(popup, appName, error instanceof Error ? error.message : '远程应用启动失败')
    throw error
  } finally {
    launchLock.delete(appId)
  }
}
