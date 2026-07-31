<template>
  <section class="file-browser">
    <header class="file-browser__toolbar">
      <nav class="file-browser__breadcrumbs" aria-label="用户空间路径">
        <button type="button" data-testid="breadcrumb-root" @click="$emit('navigate', '')">根目录</button>
        <template v-for="crumb in breadcrumbs" :key="crumb.path">
          <span>/</span>
          <button
            type="button"
            :data-testid="`breadcrumb-${crumb.name}`"
            @click="$emit('navigate', crumb.path)"
          >
            {{ crumb.name }}
          </button>
        </template>
      </nav>

      <div class="file-browser__actions">
        <button type="button" @click="$emit('refresh')">刷新</button>
        <button type="button" data-testid="mkdir-button" @click="handleCreateDirectory">新建文件夹</button>
        <label class="file-browser__upload">
          上传
          <input type="file" multiple @change="handleUpload" />
        </label>
      </div>
    </header>

    <div v-if="errorMessage" class="file-browser__error">{{ errorMessage }}</div>
    <div v-else-if="loading" class="file-browser__empty">加载中...</div>
    <div v-else-if="items.length === 0" class="file-browser__empty">当前目录为空</div>
    <table v-else class="file-browser__table">
      <thead>
        <tr>
          <th>名称</th>
          <th>类型</th>
          <th>大小</th>
          <th>修改时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.name">
          <td>
            <button
              v-if="item.is_dir"
              type="button"
              :data-testid="`entry-open-${item.name}`"
              class="file-browser__entry"
              @click="$emit('open-directory', item)"
            >
              📁 {{ item.name }}
            </button>
            <span v-else>📄 {{ item.name }}</span>
          </td>
          <td>{{ item.is_dir ? '文件夹' : '文件' }}</td>
          <td>{{ item.is_dir ? '-' : formatSize(item.size) }}</td>
          <td>{{ formatTime(item.mtime) }}</td>
          <td class="file-browser__row-actions">
            <button
              v-if="!item.is_dir && isViewerFile(item.name)"
              type="button"
              :data-testid="`view-${item.name}`"
              @click="$emit('view-entry', item)"
            >
              查看
            </button>
            <button
              v-if="!item.is_dir"
              type="button"
              :data-testid="`download-${item.name}`"
              @click="$emit('download-entry', item)"
            >
              下载
            </button>
            <button type="button" :data-testid="`move-${item.name}`" @click="handleMove(item)">移动</button>
            <button type="button" :data-testid="`delete-${item.name}`" @click="handleDelete(item)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <MoveEntryDialog
      :item="movingItem"
      :current-path="currentPath"
      :directory-loader="directoryLoader"
      @close="movingItem = null"
      @move-entry="handleMoveEntry"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import MoveEntryDialog from '@/modules/my/components/MoveEntryDialog.vue'
import type { MoveEntryPayload, WorkspaceFileItem } from '@/modules/my/types/files'

const props = defineProps<{
  currentPath: string
  items: WorkspaceFileItem[]
  loading: boolean
  errorMessage: string
  directoryLoader: (path: string) => Promise<WorkspaceFileItem[]>
}>()

const emit = defineEmits<{
  refresh: []
  navigate: [path: string]
  'open-directory': [item: WorkspaceFileItem]
  'create-directory': [name: string]
  'delete-entry': [item: WorkspaceFileItem]
  'download-entry': [item: WorkspaceFileItem]
  'view-entry': [item: WorkspaceFileItem]
  'move-entry': [payload: MoveEntryPayload]
  'upload-files': [files: File[]]
}>()

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').trim().replace(/^\/+/, '').replace(/\/+$/, '')
}

const movingItem = ref<WorkspaceFileItem | null>(null)

const breadcrumbs = computed(() => {
  const parts = normalizePath(props.currentPath).split('/').filter(Boolean)
  return parts.map((name, index) => ({
    name,
    path: parts.slice(0, index + 1).join('/'),
  }))
})

function handleCreateDirectory() {
  const name = window.prompt('请输入文件夹名称')
  const normalized = name ? normalizePath(name) : ''

  if (normalized) {
    emit('create-directory', normalized)
  }
}

function handleMove(item: WorkspaceFileItem) {
  movingItem.value = item
}

function handleMoveEntry(payload: MoveEntryPayload) {
  emit('move-entry', payload)
  movingItem.value = null
}

function handleDelete(item: WorkspaceFileItem) {
  if (window.confirm(`确认删除 ${item.name}？`)) {
    emit('delete-entry', item)
  }
}

function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])

  if (files.length > 0) {
    emit('upload-files', files)
  }
  input.value = ''
}

function formatSize(size: number) {
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1048576) {
    return `${(size / 1024).toFixed(1)} KB`
  }
  if (size < 1073741824) {
    return `${(size / 1048576).toFixed(1)} MB`
  }
  return `${(size / 1073741824).toFixed(2)} GB`
}

function formatTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString()
}

function isViewerFile(name: string) {
  return ['.vtp', '.vtu', '.stl', '.obj'].some((suffix) => name.toLowerCase().endsWith(suffix))
}
</script>

<style scoped>
.file-browser {
  display: grid;
  gap: 16px;
}

.file-browser__toolbar,
.file-browser__actions,
.file-browser__breadcrumbs {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.file-browser__toolbar {
  justify-content: space-between;
}

button,
.file-browser__upload {
  min-height: 40px;
  border: 1px solid var(--portal-color-border);
  border-radius: 999px;
  background: var(--portal-color-surface);
  color: var(--portal-color-ink);
  padding: 0 14px;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

button:hover,
.file-browser__upload:hover {
  border-color: var(--portal-color-primary);
  color: var(--portal-color-primary);
}

.file-browser__upload input {
  display: none;
}

.file-browser__table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border: 1px solid var(--portal-color-border);
  border-radius: 20px;
  background: var(--portal-color-surface);
  box-shadow: var(--portal-shadow-soft);
}

.file-browser__table th,
.file-browser__table td {
  padding: 12px;
  border-bottom: 1px solid var(--portal-color-border);
  text-align: left;
}

.file-browser__table th {
  background: var(--portal-color-page);
  color: var(--portal-color-muted);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.file-browser__entry {
  border: 0;
  padding: 0;
  background: transparent;
  border-radius: 0;
}

.file-browser__row-actions {
  display: flex;
  gap: 8px;
}

.file-browser__empty,
.file-browser__error {
  padding: 24px;
  border-radius: 18px;
  background: var(--portal-color-surface-soft);
  color: var(--portal-color-body);
}

.file-browser__error {
  color: var(--portal-color-danger);
  background: #fff5f7;
}
</style>
