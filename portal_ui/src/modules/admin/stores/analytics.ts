import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getAdminAnalyticsOverview } from '@/modules/admin/services/api/analytics'
import type { AdminAnalyticsOverviewResponse } from '@/modules/admin/types/analytics'

export const useAdminAnalyticsStore = defineStore('admin-analytics', () => {
  const overview = ref<AdminAnalyticsOverviewResponse | null>(null)
  const loading = ref(false)
  const errorMessage = ref('')

  async function loadOverview() {
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await getAdminAnalyticsOverview()
      overview.value = response.data
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载统计看板失败'
      overview.value = null
    } finally {
      loading.value = false
    }
  }

  return {
    overview,
    loading,
    errorMessage,
    loadOverview,
  }
})
