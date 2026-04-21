<template>
  <section class="admin-ops-view">
    <header class="admin-ops-view__header">
      <div>
        <h1>资源监控</h1>
        <p>会话监控和资源占用，不做花架子。</p>
      </div>
      <div class="admin-monitor__toolbar">
        <select v-model="refreshInterval" data-testid="admin-monitor-interval">
          <option value="10">10s 刷新</option>
          <option value="30">30s 刷新</option>
          <option value="60">60s 刷新</option>
        </select>
        <button type="button" @click="monitorStore.loadMonitor">刷新</button>
      </div>
    </header>

    <div v-if="monitorStore.errorMessage" class="admin-ops-view__state admin-ops-view__state--error">
      {{ monitorStore.errorMessage }}
    </div>
    <template v-else>
      <div class="admin-ops-view__summary">
        <strong>在线 {{ monitorStore.overview?.total_online || 0 }} 人</strong>
        <span>{{ monitorStore.overview?.total_sessions || 0 }} 个会话</span>
      </div>
      <div class="admin-ops-view__cards">
        <article v-for="app in monitorStore.overview?.apps || []" :key="app.app_id" class="admin-ops-view__card">
          <strong>{{ app.app_name }}</strong>
          <span>{{ app.active_count }} 活跃</span>
        </article>
      </div>
      <table class="admin-ops-view__table">
        <thead>
          <tr>
            <th>用户</th>
            <th>应用</th>
            <th>开始时间</th>
            <th>持续时间</th>
            <th>最近心跳</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="monitorStore.sessions.length === 0">
            <td colspan="7">暂无活跃会话</td>
          </tr>
          <tr v-for="session in sessionRows" :key="session.sessionId">
            <td>{{ session.displayName }}</td>
            <td>{{ session.appName }}</td>
            <td>{{ session.startedAt }}</td>
            <td>{{ session.durationText }}</td>
            <td>{{ session.lastHeartbeat }}</td>
            <td>
              <span :class="['admin-monitor__badge', session.statusTone]">{{ session.statusLabel }}</span>
            </td>
            <td>
              <button
                v-if="session.reclaimable"
                type="button"
                :data-testid="`admin-session-reclaim-${session.sessionId}`"
                @click="monitorStore.reclaimSession(session.sessionId)"
              >
                回收
              </button>
              <span v-else class="admin-monitor__muted">-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { useAdminMonitorStore } from '@/modules/admin/stores/monitor'

const monitorStore = useAdminMonitorStore()
const refreshInterval = ref('30')
let refreshTimer: number | null = null

function formatDuration(seconds: number) {
  if (!seconds || seconds < 0) return '0s'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainSeconds = seconds % 60
  if (hours) return `${hours}h ${minutes}m ${remainSeconds}s`
  if (minutes) return `${minutes}m ${remainSeconds}s`
  return `${remainSeconds}s`
}

function buildSessionStatusMeta(status: string) {
  const normalized = String(status || '').trim().toLowerCase()
  if (normalized === 'active') return { label: '在线', tone: 'admin-monitor__badge--active', reclaimable: true }
  if (normalized === 'reclaim_pending') return { label: '回收中', tone: 'admin-monitor__badge--warning', reclaimable: false }
  if (normalized === 'reclaimed') return { label: '已回收', tone: 'admin-monitor__badge--inactive', reclaimable: false }
  if (normalized === 'disconnected') return { label: '已断开', tone: 'admin-monitor__badge--inactive', reclaimable: false }
  return { label: status || '未知', tone: 'admin-monitor__badge--inactive', reclaimable: false }
}

const sessionRows = computed(() => {
  return monitorStore.sessions.map((session) => {
    const statusMeta = buildSessionStatusMeta(session.status)
    return {
      sessionId: session.session_id,
      displayName: session.display_name || session.username,
      appName: session.app_name || '',
      startedAt: session.started_at || '',
      durationText: formatDuration(session.duration_seconds),
      lastHeartbeat: session.last_heartbeat || '-',
      statusLabel: statusMeta.label,
      statusTone: statusMeta.tone,
      reclaimable: statusMeta.reclaimable,
    }
  })
})

function stopRefreshTimer() {
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
}

function restartRefreshTimer() {
  stopRefreshTimer()
  const seconds = Number.parseInt(refreshInterval.value, 10) || 30
  refreshTimer = window.setInterval(() => {
    void monitorStore.loadMonitor()
  }, seconds * 1000)
}

onMounted(async () => {
  await monitorStore.loadMonitor()
  restartRefreshTimer()
})

watch(refreshInterval, () => {
  restartRefreshTimer()
})

onUnmounted(() => {
  stopRefreshTimer()
})
</script>

<style scoped>
@import './admin-ops.css';

.admin-monitor__toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.admin-monitor__toolbar select {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  padding: 8px 10px;
}

.admin-monitor__badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fee2e2;
  color: #991b1b;
  font-size: 12px;
}

.admin-monitor__badge--active {
  background: #dcfce7;
  color: #166534;
}

.admin-monitor__badge--warning {
  background: #fef3c7;
  color: #92400e;
}

.admin-monitor__badge--inactive {
  background: #e2e8f0;
  color: #475569;
}

.admin-monitor__muted {
  color: #94a3b8;
}
</style>
