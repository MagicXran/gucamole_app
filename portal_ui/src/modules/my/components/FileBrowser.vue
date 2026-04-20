<template>
  <section class="file-browser">
    <header class="file-browser__toolbar">
      <nav class="file-browser__breadcrumbs" aria-label="个人空间路径">
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
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { MoveEntryPayload, WorkspaceFileItem } from '@/modules/my/types/files'

const props = defineProps<{
  currentPath: string
  items: WorkspaceFileItem[]
  loading: boolean
  errorMessage: string
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
  const sourcePath = joinPath(props.currentPath, item.name)
  const targetPath = window.prompt('请输入目标路径', sourcePath)
  const normalizedTarget = targetPath ? normalizePath(targetPath) : ''

  if (normalizedTarget) {
    emit('move-entry', {
      sourcePath,
      targetPath: normalizedTarget,
    })
  }
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
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #1e3a8a;
  padding: 8px 12px;
  cursor: pointer;
}

.file-browser__upload input {
  display: none;
}

.file-browser__table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}

.file-browser__table th,
.file-browser__table td {
  padding: 12px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
}

.file-browser__entry {
  border: 0;
  padding: 0;
}

.file-browser__row-actions {
  display: flex;
  gap: 8px;
}

.file-browser__empty,
.file-browser__error {
  padding: 24px;
  border-radius: 14px;
  background: #f8fafc;
  color: #64748b;
}

.file-browser__error {
  color: #b91c1c;
  background: #fef2f2;
}
</style>
