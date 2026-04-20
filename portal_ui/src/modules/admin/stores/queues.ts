import { defineStore } from 'pinia'
import { ref } from 'vue'

import { cancelAdminQueue, listAdminQueues } from '@/modules/admin/services/api/ops'
import type { AdminQueueItem } from '@/modules/admin/types/ops'

export const useAdminQueuesStore = defineStore('admin-queues', () => {
  const items = ref<AdminQueueItem[]>([])
  const loading = ref(false)
  const errorMessage = ref('')

  async function loadQueues() {
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await listAdminQueues()
      items.value = response.data.items || []
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载排队明细失败'
      items.value = []
    } finally {
      loading.value = false
    }
  }

  async function cancelQueue(queueId: number) {
    await cancelAdminQueue(queueId)
    await loadQueues()
  }

  return {
    items,
    loading,
    errorMessage,
    loadQueues,
    cancelQueue,
  }
})
