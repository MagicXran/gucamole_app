import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { listRemoteApps } from '@/services/api/compute'
import type { ComputeAppCard } from '@/types/compute'

type LoadAppsOptions = {
  background?: boolean
}

function resolveErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : '加载应用失败'
}

export const useComputeStore = defineStore('compute', () => {
  const apps = ref<ComputeAppCard[]>([])
  const query = ref('')
  const loading = ref(false)
  const refreshing = ref(false)
  const loaded = ref(false)
  const errorMessage = ref('')
  const refreshErrorMessage = ref('')

  const filteredApps = computed(() => {
    const keyword = query.value.trim().toLowerCase()

    if (!keyword) {
      return apps.value
    }

    return apps.value.filter((app) => app.name.toLowerCase().includes(keyword))
  })

  async function loadApps(options: LoadAppsOptions = {}) {
    if (loading.value || refreshing.value) {
      return
    }

    const useBackgroundState = Boolean(options.background && loaded.value && apps.value.length > 0)
    if (useBackgroundState) {
      refreshing.value = true
      refreshErrorMessage.value = ''
    } else {
      loading.value = true
      errorMessage.value = ''
    }

    try {
      const response = await listRemoteApps()
      apps.value = response.data
      errorMessage.value = ''
      refreshErrorMessage.value = ''
    } catch (error) {
      const message = resolveErrorMessage(error)
      if (useBackgroundState) {
        refreshErrorMessage.value = message
      } else {
        apps.value = []
        errorMessage.value = message
      }
    } finally {
      loaded.value = true
      if (useBackgroundState) {
        refreshing.value = false
      } else {
        loading.value = false
      }
    }
  }

  function getAppByPoolId(poolId: number) {
    return apps.value.find((app) => app.pool_id === poolId)
  }

  async function refreshApps() {
    await loadApps({ background: true })
  }

  return {
    apps,
    query,
    loading,
    refreshing,
    loaded,
    errorMessage,
    refreshErrorMessage,
    filteredApps,
    loadApps,
    refreshApps,
    getAppByPoolId,
  }
})
