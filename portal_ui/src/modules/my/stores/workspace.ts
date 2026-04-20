import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  cancelUpload,
  createDirectory,
  deleteFile,
  getSpaceInfo,
  listFiles,
  moveFile,
  requestDownloadToken,
  uploadChunk,
  uploadInit,
} from '@/modules/my/services/api/files'
import type { MoveEntryPayload, WorkspaceFileItem, WorkspaceSpaceInfo } from '@/modules/my/types/files'

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').trim().replace(/^\/+/, '').replace(/\/+$/, '')
}

function joinPath(base: string, name: string) {
  const cleanedName = normalizePath(name)
  const cleanedBase = normalizePath(base)

  if (!cleanedBase) {
    return cleanedName
  }
  if (!cleanedName) {
    return cleanedBase
  }
  return `${cleanedBase}/${cleanedName}`
}

function resolveErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message
  }
  return '个人空间操作失败'
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const currentPath = ref('')
  const items = ref<WorkspaceFileItem[]>([])
  const quota = ref<WorkspaceSpaceInfo | null>(null)
  const quotaErrorMessage = ref('')
  const loading = ref(false)
  const uploading = ref(false)
  const errorMessage = ref('')

  const isRoot = computed(() => !currentPath.value)

  function toCurrentPath(nameOrPath: string) {
    const normalized = normalizePath(nameOrPath)

    if (!currentPath.value || normalized.startsWith(`${currentPath.value}/`) || normalized === currentPath.value) {
      return normalized
    }
    return joinPath(currentPath.value, normalized)
  }

  async function loadQuota(refresh = false) {
    quotaErrorMessage.value = ''

    try {
      const response = await getSpaceInfo(refresh)
      quota.value = response.data
    } catch (error) {
      quota.value = null
      quotaErrorMessage.value = resolveErrorMessage(error)
    }
  }

  async function loadDirectory(path = '') {
    loading.value = true
    errorMessage.value = ''

    try {
      const normalized = normalizePath(path)
      const response = await listFiles(normalized)
      currentPath.value = normalizePath(response.data.path)
      items.value = response.data.items
    } catch (error) {
      items.value = []
      errorMessage.value = resolveErrorMessage(error)
    } finally {
      loading.value = false
    }
  }

  async function refresh() {
    await Promise.all([loadQuota(true), loadDirectory(currentPath.value)])
  }

  async function createFolder(name: string) {
    await runAction(async () => {
      const targetPath = joinPath(currentPath.value, name)
      await createDirectory(targetPath)
      await refresh()
    })
  }

  async function deleteEntry(item: WorkspaceFileItem) {
    await runAction(async () => {
      await deleteFile(joinPath(currentPath.value, item.name))
      await refresh()
    })
  }

  async function moveEntry(payload: MoveEntryPayload) {
    await runAction(async () => {
      await moveFile(toCurrentPath(payload.sourcePath), normalizePath(payload.targetPath))
      await refresh()
    })
  }

  async function downloadEntry(item: WorkspaceFileItem) {
    await runAction(async () => {
      const response = await requestDownloadToken(joinPath(currentPath.value, item.name))
      const token = encodeURIComponent(response.data.token)
      window.open(`/api/files/download?_token=${token}`, '_blank', 'noopener')
    })
  }

  async function uploadFiles(files: File[]) {
    if (files.length === 0) {
      return
    }

    uploading.value = true
    errorMessage.value = ''

    try {
      for (const file of files) {
        await uploadOneFile(file)
      }
      await refresh()
    } catch (error) {
      errorMessage.value = resolveErrorMessage(error)
    } finally {
      uploading.value = false
    }
  }

  async function runAction(action: () => Promise<void>) {
    errorMessage.value = ''

    try {
      await action()
    } catch (error) {
      errorMessage.value = resolveErrorMessage(error)
    }
  }

  async function uploadOneFile(file: File) {
    const targetPath = joinPath(currentPath.value, file.name)
    const initResponse = await uploadInit(targetPath, file.size)
    const uploadId = initResponse.data.upload_id
    const chunkSize = Math.max(initResponse.data.chunk_size, 1)
    let offset = initResponse.data.offset

    try {
      while (offset < file.size) {
        const nextChunk = file.slice(offset, Math.min(offset + chunkSize, file.size))
        const chunkResponse = await uploadChunk(uploadId, offset, nextChunk)
        offset = chunkResponse.data.offset

        if (chunkResponse.data.complete) {
          break
        }
      }
    } catch (error) {
      await cancelUpload(uploadId)
      throw error
    }
  }

  return {
    currentPath,
    items,
    quota,
    quotaErrorMessage,
    loading,
    uploading,
    errorMessage,
    isRoot,
    loadQuota,
    loadDirectory,
    refresh,
    createFolder,
    deleteEntry,
    moveEntry,
    downloadEntry,
    uploadFiles,
  }
})
