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

    <section
      v-if="workspace.uploadTasks.length > 0"
      class="workspace-upload-panel"
      aria-live="polite"
      data-testid="workspace-upload-panel"
    >
      <div class="workspace-upload-panel__header">
        <strong>上传队列</strong>
        <span>{{ uploadSummary }}</span>
      </div>
      <article
        v-for="task in workspace.uploadTasks"
        :key="task.id"
        class="workspace-upload-card"
        :class="`workspace-upload-card--${task.status}`"
        :data-testid="`upload-task-${task.name}`"
      >
        <div class="workspace-upload-card__topline">
          <strong>{{ task.name }}</strong>
          <span>{{ formatUploadStatus(task) }}</span>
        </div>
        <div class="workspace-upload-card__bar" :aria-label="`${task.name} 上传进度 ${uploadPercent(task)}%`">
          <div class="workspace-upload-card__fill" :style="{ width: `${uploadPercent(task)}%` }"></div>
        </div>
        <div class="workspace-upload-card__meta">
          <span>{{ formatUploadBytes(task) }}</span>
          <span>{{ formatUploadSpeed(task) }}</span>
        </div>
      </article>
    </section>

    <FileBrowser
      :current-path="workspace.currentPath"
      :items="workspace.items"
      :loading="workspace.loading"
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
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FileBrowser from '@/modules/my/components/FileBrowser.vue'
import { useWorkspaceStore } from '@/modules/my/stores/workspace'
import type { MoveEntryPayload, WorkspaceFileItem, WorkspaceUploadTask } from '@/modules/my/types/files'

const route = useRoute()
const router = useRouter()
const workspace = useWorkspaceStore()

const uploadSummary = computed(() => {
  const active = workspace.uploadTasks.filter((task) => task.status === 'preparing' || task.status === 'uploading').length
  const done = workspace.uploadTasks.filter((task) => task.status === 'done').length
  const failed = workspace.uploadTasks.filter((task) => task.status === 'error').length
  return `进行中 ${active}，完成 ${done}，失败 ${failed}`
})

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

function uploadPercent(task: WorkspaceUploadTask) {
  if (task.size <= 0) {
    return task.status === 'done' ? 100 : 0
  }
  return Math.min(Math.round((task.uploadedBytes / task.size) * 100), 100)
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1048576) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  if (bytes < 1073741824) {
    return `${(bytes / 1048576).toFixed(1)} MB`
  }
  return `${(bytes / 1073741824).toFixed(2)} GB`
}

function formatUploadBytes(task: WorkspaceUploadTask) {
  return `${formatBytes(task.uploadedBytes)} / ${formatBytes(task.size)}`
}

function formatUploadSpeed(task: WorkspaceUploadTask) {
  if (task.status === 'preparing') {
    return '准备中'
  }
  if (task.status === 'done') {
    return '完成'
  }
  if (task.status === 'error') {
    return '失败'
  }
  if (task.speedBytesPerSecond <= 0) {
    return '计算速度中'
  }
  return `${formatBytes(Math.round(task.speedBytesPerSecond))}/s`
}

function formatUploadStatus(task: WorkspaceUploadTask) {
  if (task.status === 'error') {
    return task.message || '上传失败'
  }
  if (task.status === 'done') {
    return '上传完成'
  }
  if (task.status === 'preparing') {
    return '正在准备'
  }
  return `${uploadPercent(task)}%`
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

.workspace-upload-panel {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid #bfdbfe;
  border-radius: 16px;
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
}

.workspace-upload-panel__header,
.workspace-upload-card__topline,
.workspace-upload-card__meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.workspace-upload-panel__header {
  color: #1e3a8a;
}

.workspace-upload-panel__header span,
.workspace-upload-card__meta,
.workspace-upload-card__topline span {
  color: #64748b;
  font-size: 13px;
}

.workspace-upload-card {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 8px 20px rgba(30, 58, 138, 0.08);
}

.workspace-upload-card--done {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.workspace-upload-card--error {
  border-color: #fecaca;
  background: #fef2f2;
}

.workspace-upload-card--error .workspace-upload-card__topline span {
  color: #b91c1c;
}

.workspace-upload-card__topline strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #0f172a;
}

.workspace-upload-card__bar {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #dbeafe;
}

.workspace-upload-card__fill {
  height: 100%;
  min-width: 10px;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #38bdf8, #2563eb);
  background-size: 220% 100%;
  transition: width 0.24s ease;
  animation: upload-flow 1.1s linear infinite;
}

.workspace-upload-card--done .workspace-upload-card__fill {
  background: #16a34a;
  animation: none;
}

.workspace-upload-card--error .workspace-upload-card__fill {
  background: #dc2626;
  animation: none;
}

@keyframes upload-flow {
  from {
    background-position: 0 0;
  }
  to {
    background-position: 220% 0;
  }
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
