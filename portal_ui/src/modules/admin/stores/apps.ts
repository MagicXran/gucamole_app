import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  createAdminApp,
  deleteAdminApp,
  listAdminApps,
  listAdminPools,
  listAdminScriptProfiles,
  listAdminWorkerGroups,
  updateAdminApp,
} from '@/modules/admin/services/api/apps'
import type {
  AdminAppFormPayload,
  AdminAppRecord,
  AdminPoolRecord,
  AdminScriptProfile,
  AdminWorkerGroup,
  PoolAttachments,
} from '@/modules/admin/types/apps'

export function emptyPoolAttachments(poolId = 0): PoolAttachments {
  return {
    pool_id: poolId,
    tutorial_docs: [],
    video_resources: [],
    plugin_downloads: [],
  }
}

export function clonePoolAttachments(payload: PoolAttachments): PoolAttachments {
  return {
    pool_id: payload.pool_id,
    tutorial_docs: payload.tutorial_docs.map((item) => ({ ...item })),
    video_resources: payload.video_resources.map((item) => ({ ...item })),
    plugin_downloads: payload.plugin_downloads.map((item) => ({ ...item })),
  }
}

export const useAdminAppsStore = defineStore('admin-apps', () => {
  const items = ref<AdminAppRecord[]>([])
  const pools = ref<AdminPoolRecord[]>([])
  const workerGroups = ref<AdminWorkerGroup[]>([])
  const scriptProfiles = ref<AdminScriptProfile[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const errorMessage = ref('')

  async function loadApps() {
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await listAdminApps()
      items.value = response.data
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载应用失败'
      items.value = []
    } finally {
      loading.value = false
    }
  }

  async function loadPools() {
    try {
      const response = await listAdminPools()
      pools.value = response.data
    } catch {
      pools.value = []
    }
  }

  async function loadWorkerGroups() {
    try {
      const response = await listAdminWorkerGroups()
      workerGroups.value = response.data.items
    } catch {
      workerGroups.value = []
    }
  }

  async function loadScriptProfiles() {
    try {
      const response = await listAdminScriptProfiles()
      scriptProfiles.value = response.data.items
    } catch {
      scriptProfiles.value = []
    }
  }

  async function bootstrap() {
    await Promise.all([loadApps(), loadPools(), loadWorkerGroups(), loadScriptProfiles()])
  }

  async function saveApp(appId: number | null, payload: AdminAppFormPayload) {
    saving.value = true
    errorMessage.value = ''
    try {
      const response = appId
        ? await updateAdminApp(appId, payload)
        : await createAdminApp(payload)
      await loadApps()
      return response.data
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '保存应用失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  async function removeApp(appId: number) {
    saving.value = true
    errorMessage.value = ''
    try {
      await deleteAdminApp(appId)
      await loadApps()
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '删除应用失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  return {
    items,
    pools,
    workerGroups,
    scriptProfiles,
    loading,
    saving,
    errorMessage,
    bootstrap,
    loadApps,
    loadWorkerGroups,
    loadScriptProfiles,
    saveApp,
    removeApp,
  }
})
