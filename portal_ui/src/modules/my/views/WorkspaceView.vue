<template>
  <section class="workspace-view">
    <header class="workspace-view__header">
      <div>
        <h1>个人空间</h1>
        <p>浏览、上传、下载、移动和整理你的远程应用文件。</p>
      </div>
      <div v-if="workspace.quota" class="workspace-view__quota">
        <strong>{{ workspace.quota.used_display }}</strong>
        <span>/ {{ workspace.quota.quota_display }}</span>
        <span>{{ workspace.quota.usage_percent }}%</span>
      </div>
    </header>

    <div class="workspace-view__path">
      当前路径：<code>{{ workspace.currentPath || '根目录' }}</code>
    </div>

    <FileBrowser
      :current-path="workspace.currentPath"
      :items="workspace.items"
      :loading="workspace.loading || workspace.uploading"
      :error-message="workspace.errorMessage"
      @refresh="handleRefresh"
      @navigate="handleNavigate"
      @open-directory="handleOpenDirectory"
      @create-directory="handleCreateDirectory"
      @delete-entry="handleDeleteEntry"
      @download-entry="handleDownloadEntry"
      @view-entry="handleViewEntry"
      @move-entry="handleMoveEntry"
      @upload-files="handleUploadFiles"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FileBrowser from '@/modules/my/components/FileBrowser.vue'
import { useWorkspaceStore } from '@/modules/my/stores/workspace'
import type { MoveEntryPayload, WorkspaceFileItem } from '@/modules/my/types/files'

const route = useRoute()
const router = useRouter()
const workspace = useWorkspaceStore()

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').trim().replace(/^\/+/, '').replace(/\/+$/, '')
}

function queryPath() {
  return typeof route.query.path === 'string' ? normalizePath(route.query.path) : ''
}

function joinPath(base: string, name: string) {
  const cleanedBase = normalizePath(base)
  const cleanedName = normalizePath(name)

  if (!cleanedBase) {
    return cleanedName
  }
  if (!cleanedName) {
    return cleanedBase
  }
  return `${cleanedBase}/${cleanedName}`
}

async function syncRoutePath(path: string) {
  const normalized = normalizePath(path)
  const current = queryPath()

  if (normalized === current) {
    return
  }

  await router.replace({
    path: '/my/workspace',
    query: normalized ? { path: normalized } : {},
  })
}

async function loadPath(path: string) {
  await workspace.loadDirectory(path)
  await syncRoutePath(workspace.currentPath)
}

async function handleRefresh() {
  await workspace.refresh()
}

async function handleNavigate(path: string) {
  await loadPath(path)
}

async function handleOpenDirectory(item: WorkspaceFileItem) {
  if (!item.is_dir) {
    return
  }

  await loadPath(joinPath(workspace.currentPath, item.name))
}

async function handleCreateDirectory(name: string) {
  await workspace.createFolder(name)
}

async function handleDeleteEntry(item: WorkspaceFileItem) {
  await workspace.deleteEntry(item)
}

async function handleDownloadEntry(item: WorkspaceFileItem) {
  await workspace.downloadEntry(item)
}

function handleViewEntry(item: WorkspaceFileItem) {
  if (item.is_dir) {
    return
  }
  const fullPath = joinPath(workspace.currentPath, item.name)
  window.open(`/viewer.html?path=${encodeURIComponent(fullPath)}`, '_blank', 'noopener')
}

async function handleMoveEntry(payload: MoveEntryPayload) {
  await workspace.moveEntry(payload)
}

async function handleUploadFiles(files: File[]) {
  await workspace.uploadFiles(files)
}

onMounted(async () => {
  await Promise.all([workspace.loadQuota(), workspace.loadDirectory(queryPath())])
})

watch(
  () => route.query.path,
  async () => {
    const nextPath = queryPath()
    if (nextPath !== workspace.currentPath) {
      await workspace.loadDirectory(nextPath)
    }
  },
)
</script>

<style scoped>
.workspace-view {
  display: grid;
  gap: 18px;
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.workspace-view__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.workspace-view__quota {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 12px 14px;
  border-radius: 14px;
  background: #eff6ff;
  color: #1e3a8a;
}

.workspace-view__path {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f8fafc;
  color: #475569;
}

h1 {
  margin: 0 0 12px;
  font-size: 32px;
  color: #1e3a8a;
}

p {
  margin: 0;
  color: #475569;
}

code {
  color: #0f172a;
}
</style>
