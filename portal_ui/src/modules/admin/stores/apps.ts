import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  createAdminApp,
  deleteAdminApp,
  getAdminPoolAttachments,
  listAdminApps,
  listAdminPools,
  replaceAdminPoolAttachments,
  updateAdminApp,
} from '@/modules/admin/services/api/apps'
import type { AdminAppFormPayload, AdminAppRecord, AdminPoolRecord, AttachmentItemDraft, PoolAttachments } from '@/modules/admin/types/apps'

function normalizeAttachmentItems(items: AttachmentItemDraft[]) {
  return items
    .map((item, index) => ({
      title: String(item.title || '').trim(),
      summary: String(item.summary || '').trim(),
      link_url: String(item.link_url || '').trim(),
      sort_order: index,
    }))
    .filter((item) => item.title || item.link_url)
}

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

function normalizePoolAttachments(payload: PoolAttachments, poolId: number): PoolAttachments {
  return {
    pool_id: poolId,
    tutorial_docs: normalizeAttachmentItems(payload.tutorial_docs),
    video_resources: normalizeAttachmentItems(payload.video_resources),
    plugin_downloads: normalizeAttachmentItems(payload.plugin_downloads),
  }
}

export const useAdminAppsStore = defineStore('admin-apps', () => {
  const items = ref<AdminAppRecord[]>([])
  const pools = ref<AdminPoolRecord[]>([])
  const attachments = ref<PoolAttachments>(emptyPoolAttachments())
  const loading = ref(false)
  const attachmentsLoading = ref(false)
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

  async function bootstrap() {
    await Promise.all([loadApps(), loadPools()])
  }

  async function loadPoolAttachments(poolId: number | null) {
    if (!poolId) {
      attachments.value = emptyPoolAttachments()
      return attachments.value
    }
    attachmentsLoading.value = true
    try {
      const response = await getAdminPoolAttachments(poolId)
      attachments.value = clonePoolAttachments(response.data)
      return attachments.value
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载资源池附件失败'
      attachments.value = emptyPoolAttachments(poolId)
      return attachments.value
    } finally {
      attachmentsLoading.value = false
    }
  }

  async function saveApp(
    appId: number | null,
    payload: AdminAppFormPayload,
    attachmentPayload: PoolAttachments,
    attachmentPoolId: number | null = payload.pool_id,
  ) {
    saving.value = true
    errorMessage.value = ''
    try {
      const response = appId
        ? await updateAdminApp(appId, payload)
        : await createAdminApp(payload)

      if (attachmentPoolId) {
        const normalizedAttachments = normalizePoolAttachments(attachmentPayload, attachmentPoolId)
        const attachmentResponse = await replaceAdminPoolAttachments(attachmentPoolId, normalizedAttachments)
        attachments.value = clonePoolAttachments(attachmentResponse.data)
      } else {
        attachments.value = emptyPoolAttachments()
      }

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
    attachments,
    loading,
    attachmentsLoading,
    saving,
    errorMessage,
    bootstrap,
    loadApps,
    loadPoolAttachments,
    saveApp,
    removeApp,
  }
})
