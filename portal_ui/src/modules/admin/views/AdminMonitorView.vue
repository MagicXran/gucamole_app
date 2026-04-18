<template>
  <section class="admin-ops-view">
    <header class="admin-ops-view__header">
      <div>
        <h1>资源监控</h1>
        <p>会话监控和资源占用，不做花架子。</p>
      </div>
      <button type="button" @click="monitorStore.loadMonitor">刷新</button>
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
            <th>状态</th>
            <th>最近心跳</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="monitorStore.sessions.length === 0">
            <td colspan="5">暂无活跃会话</td>
          </tr>
          <tr v-for="session in monitorStore.sessions" :key="session.session_id">
            <td>{{ session.display_name || session.username }}</td>
            <td>{{ session.app_name }}</td>
            <td>{{ session.status }}</td>
            <td>{{ session.last_heartbeat || '-' }}</td>
            <td>
              <button
                type="button"
                :data-testid="`admin-session-reclaim-${session.session_id}`"
                @click="monitorStore.reclaimSession(session.session_id)"
              >
                回收
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import { useAdminMonitorStore } from '@/modules/admin/stores/monitor'

const monitorStore = useAdminMonitorStore()

onMounted(async () => {
  await monitorStore.loadMonitor()
})
</script>

<style scoped>
@import './admin-ops.css';
</style>
