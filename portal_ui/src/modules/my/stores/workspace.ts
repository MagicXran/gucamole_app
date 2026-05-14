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
import type {
  MoveEntryPayload,
  WorkspaceFileItem,
  WorkspaceSpaceInfo,
  WorkspaceUploadTask,
} from '@/modules/my/types/files'

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
  const errorMessage = ref('')
  const uploadTasks = ref<WorkspaceUploadTask[]>([])

  const isRoot = computed(() => !currentPath.value)
  const uploading = computed(() =>
    uploadTasks.value.some((task) => task.status === 'preparing' || task.status === 'uploading'),
  )

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

    errorMessage.value = ''

    try {
      for (const file of files) {
        await uploadOneFile(file)
      }
      await refresh()
    } catch (error) {
      errorMessage.value = resolveErrorMessage(error)
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
    const task = createUploadTask(file)
    let uploadId = ''

    try {
      const initResponse = await uploadInit(targetPath, file.size)
      uploadId = initResponse.data.upload_id
      const chunkSize = Math.max(initResponse.data.chunk_size, 1)
      let offset = initResponse.data.offset
      updateUploadTask(task.id, {
        uploadId,
        uploadedBytes: offset,
        lastProgressBytes: offset,
        status: 'uploading',
        message: '正在上传',
      })

      while (offset < file.size) {
        const nextChunk = file.slice(offset, Math.min(offset + chunkSize, file.size))
        const chunkOffset = offset
        const chunkResponse = await uploadChunk(uploadId, offset, nextChunk, (event) => {
          const loaded = Math.min(nextChunk.size, Math.max(event.loaded || 0, 0))
          updateUploadProgress(task.id, chunkOffset + loaded, file.size)
        })
        offset = chunkResponse.data.offset
        updateUploadProgress(task.id, offset, file.size, true)

        if (chunkResponse.data.complete) {
          break
        }
      }
      updateUploadTask(task.id, {
        uploadedBytes: file.size,
        status: 'done',
        message: '上传完成',
        speedBytesPerSecond: 0,
      })
      window.setTimeout(() => removeUploadTask(task.id), 8000)
    } catch (error) {
      updateUploadTask(task.id, {
        status: 'error',
        message: resolveErrorMessage(error),
        speedBytesPerSecond: 0,
      })
      if (uploadId) {
        await cancelUpload(uploadId).catch(() => undefined)
      }
      throw error
    }
  }

  function createUploadTask(file: File) {
    const now = Date.now()
    const task: WorkspaceUploadTask = {
      id: `${now}-${Math.random().toString(36).slice(2, 8)}`,
      uploadId: '',
      name: file.name,
      size: file.size,
      uploadedBytes: 0,
      speedBytesPerSecond: 0,
      status: 'preparing',
      message: '正在准备上传',
      startedAt: now,
      updatedAt: now,
      lastProgressAt: now,
      lastProgressBytes: 0,
    }
    uploadTasks.value.unshift(task)
    return task
  }

  function updateUploadTask(taskId: string, patch: Partial<WorkspaceUploadTask>) {
    const task = uploadTasks.value.find((item) => item.id === taskId)
    if (!task) {
      return
    }
    Object.assign(task, patch, { updatedAt: Date.now() })
  }

  function updateUploadProgress(taskId: string, uploadedBytes: number, totalBytes: number, forceSpeed = false) {
    const task = uploadTasks.value.find((item) => item.id === taskId)
    if (!task) {
      return
    }

    const now = Date.now()
    const nextBytes = Math.min(Math.max(uploadedBytes, task.uploadedBytes), totalBytes)
    const elapsedSeconds = Math.max((now - task.lastProgressAt) / 1000, 0.001)
    const deltaBytes = nextBytes - task.lastProgressBytes

    if ((forceSpeed || now - task.lastProgressAt >= 250) && deltaBytes >= 0) {
      const instantSpeed = deltaBytes / elapsedSeconds
      task.speedBytesPerSecond = task.speedBytesPerSecond > 0
        ? task.speedBytesPerSecond * 0.65 + instantSpeed * 0.35
        : instantSpeed
      task.lastProgressAt = now
      task.lastProgressBytes = nextBytes
    }

    task.uploadedBytes = nextBytes
    task.status = 'uploading'
    task.message = '正在上传'
    task.updatedAt = now
  }

  function removeUploadTask(taskId: string) {
    uploadTasks.value = uploadTasks.value.filter((task) => task.id !== taskId)
  }

  return {
    currentPath,
    items,
    quota,
    quotaErrorMessage,
    loading,
    uploading,
    uploadTasks,
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
