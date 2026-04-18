<template>
  <aside v-if="open" class="task-detail-drawer">
    <header class="task-detail-drawer__header">
      <div>
        <h2>{{ task?.task_id || '任务详情' }}</h2>
        <p>{{ task?.status || '未选择任务' }}</p>
      </div>
      <button type="button" data-testid="task-detail-close" @click="$emit('close')">关闭</button>
    </header>

    <div v-if="loading" class="task-detail-drawer__empty">详情加载中...</div>
    <template v-else-if="task">
      <div v-if="errorMessage" class="task-detail-drawer__error">{{ errorMessage }}</div>
      <section class="task-detail-drawer__section">
        <dl>
          <div><dt>入口文件</dt><dd>{{ task.entry_path }}</dd></div>
          <div><dt>执行器</dt><dd>{{ task.executor_key || '-' }}</dd></div>
          <div><dt>工作区</dt><dd>{{ task.workspace_path || '-' }}</dd></div>
          <div><dt>输入快照</dt><dd>{{ task.input_snapshot_path || '-' }}</dd></div>
          <div><dt>临时目录</dt><dd>{{ task.scratch_path || '-' }}</dd></div>
        </dl>
        <button
          v-if="canCancel"
          type="button"
          data-testid="task-cancel-primary"
          :disabled="cancelLoading"
          @click="$emit('cancel-task', task.task_id)"
        >
          {{ cancelLoading ? '取消中...' : '取消任务' }}
        </button>
      </section>

      <section class="task-detail-drawer__section">
        <h3>日志</h3>
        <div v-if="logs.length === 0" class="task-detail-drawer__empty">暂无日志</div>
        <ul v-else class="task-detail-drawer__list">
          <li v-for="log in logs" :key="`${log.seq_no}-${log.created_at}`">
            <strong>#{{ log.seq_no }}</strong>
            <span>[{{ log.level }}]</span>
            <span>{{ log.message }}</span>
          </li>
        </ul>
      </section>

      <section class="task-detail-drawer__section">
        <h3>结果索引</h3>
        <div v-if="artifacts.length === 0" class="task-detail-drawer__empty">暂无结果</div>
        <ul v-else class="task-detail-drawer__list">
          <li v-for="(artifact, index) in artifacts" :key="`${artifact.display_name}-${index}`">
            <div>{{ artifact.display_name }}</div>
            <div>{{ artifact.relative_path || artifact.external_url || '-' }}</div>
            <a
              v-if="artifact.external_url"
              :href="artifact.external_url"
              target="_blank"
              rel="noreferrer"
            >外部链接</a>
            <a
              v-if="workspaceHref(artifact)"
              :data-testid="`artifact-workspace-link-${index}`"
              :href="workspaceHref(artifact) || '#'
              "
            >跳到个人空间</a>
          </li>
        </ul>
      </section>
    </template>
    <div v-else-if="errorMessage" class="task-detail-drawer__error">{{ errorMessage }}</div>
    <div v-else class="task-detail-drawer__empty">请选择一个任务</div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { TaskArtifactItem, TaskDetail, TaskLogItem } from '@/modules/my/types/tasks'

const props = defineProps<{
  open: boolean
  loading: boolean
  errorMessage: string
  cancelLoading: boolean
  task: TaskDetail | null
  logs: TaskLogItem[]
  artifacts: TaskArtifactItem[]
}>()

defineEmits<{
  close: []
  'cancel-task': [taskId: string]
}>()

const cancellableStatuses = ['queued', 'submitted', 'assigned', 'preparing', 'running', 'uploading']

const canCancel = computed(() => {
  return Boolean(props.task?.task_id && props.task?.status && cancellableStatuses.includes(props.task.status))
})

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').replace(/\/+/g, '/').replace(/^\/+/, '').replace(/\/+$/, '')
}

function workspaceHref(artifact: TaskArtifactItem) {
  const relativePath = normalizePath(String(artifact.relative_path || ''))
  if (!relativePath || !relativePath.startsWith('Output/')) {
    return ''
  }

  const segments = relativePath.split('/')
  const workspacePath = segments.length > 1 ? segments.slice(0, -1).join('/') : relativePath
  return `/my/workspace?path=${encodeURIComponent(workspacePath)}`
}
</script>

<style scoped>
.task-detail-drawer {
  display: grid;
  gap: 16px;
  padding: 20px;
  border-radius: 16px;
  background: #f8fafc;
}

.task-detail-drawer__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.task-detail-drawer__section {
  display: grid;
  gap: 12px;
}

.task-detail-drawer__section dl {
  display: grid;
  gap: 8px;
}

.task-detail-drawer__section dl div {
  display: grid;
  gap: 4px;
}

.task-detail-drawer__list {
  display: grid;
  gap: 8px;
  padding-left: 18px;
}

.task-detail-drawer__empty,
.task-detail-drawer__error {
  padding: 16px;
  border-radius: 12px;
  background: #fff;
  color: #64748b;
}

.task-detail-drawer__error {
  background: #fef2f2;
  color: #b91c1c;
}

button,
a {
  width: fit-content;
}
</style>
