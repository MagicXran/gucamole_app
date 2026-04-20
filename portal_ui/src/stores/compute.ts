import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { listRemoteApps } from '@/services/api/compute'
import type { ComputeAppCard } from '@/types/compute'

function resolveErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : '加载应用失败'
}

export const useComputeStore = defineStore('compute', () => {
  const apps = ref<ComputeAppCard[]>([])
  const query = ref('')
  const loading = ref(false)
  const loaded = ref(false)
  const errorMessage = ref('')

  const filteredApps = computed(() => {
    const keyword = query.value.trim().toLowerCase()

    if (!keyword) {
      return apps.value
    }

    return apps.value.filter((app) => app.name.toLowerCase().includes(keyword))
  })

  async function loadApps() {
    loading.value = true
    errorMessage.value = ''

    try {
      const response = await listRemoteApps()
      apps.value = response.data
    } catch (error) {
      apps.value = []
      errorMessage.value = resolveErrorMessage(error)
    } finally {
      loaded.value = true
      loading.value = false
    }
  }

  function getAppByPoolId(poolId: number) {
    return apps.value.find((app) => app.pool_id === poolId)
  }

  return {
    apps,
    query,
    loading,
    loaded,
    errorMessage,
    filteredApps,
    loadApps,
    getAppByPoolId,
  }
})
