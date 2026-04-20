import { defineStore } from 'pinia'
import { ref } from 'vue'

import { listAdminWorkerGroups, listAdminWorkerNodes } from '@/modules/admin/services/api/ops'
import type { AdminWorkerGroup, AdminWorkerNode } from '@/modules/admin/types/ops'

export const useAdminWorkersStore = defineStore('admin-workers', () => {
  const groups = ref<AdminWorkerGroup[]>([])
  const nodes = ref<AdminWorkerNode[]>([])
  const loading = ref(false)
  const errorMessage = ref('')

  async function loadWorkers() {
    loading.value = true
    errorMessage.value = ''
    try {
      const [groupsResponse, nodesResponse] = await Promise.all([
        listAdminWorkerGroups(),
        listAdminWorkerNodes(),
      ])
      groups.value = groupsResponse.data.items || []
      nodes.value = nodesResponse.data.items || []
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载 Worker 状态失败'
      groups.value = []
      nodes.value = []
    } finally {
      loading.value = false
    }
  }

  return {
    groups,
    nodes,
    loading,
    errorMessage,
    loadWorkers,
  }
})
