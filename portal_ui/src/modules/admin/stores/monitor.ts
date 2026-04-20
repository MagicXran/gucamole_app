import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getAdminMonitorOverview, getAdminMonitorSessions, reclaimAdminSession } from '@/modules/admin/services/api/ops'
import type { AdminMonitorOverview, AdminMonitorSession } from '@/modules/admin/types/ops'

export const useAdminMonitorStore = defineStore('admin-monitor', () => {
  const overview = ref<AdminMonitorOverview | null>(null)
  const sessions = ref<AdminMonitorSession[]>([])
  const loading = ref(false)
  const errorMessage = ref('')

  async function loadMonitor() {
    loading.value = true
    errorMessage.value = ''
    try {
      const [overviewResponse, sessionsResponse] = await Promise.all([
        getAdminMonitorOverview(),
        getAdminMonitorSessions(),
      ])
      overview.value = overviewResponse.data
      sessions.value = sessionsResponse.data.sessions || []
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载资源监控失败'
      overview.value = null
      sessions.value = []
    } finally {
      loading.value = false
    }
  }

  async function reclaimSession(sessionId: string) {
    await reclaimAdminSession(sessionId)
    await loadMonitor()
  }

  return {
    overview,
    sessions,
    loading,
    errorMessage,
    loadMonitor,
    reclaimSession,
  }
})
