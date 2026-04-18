<template>
  <section class="task-table">
    <header class="task-table__filters">
      <label>
        状态
        <select
          :value="statusFilter"
          data-testid="task-status-filter"
          @change="$emit('update:statusFilter', ($event.target as HTMLSelectElement).value)"
        >
          <option v-for="option in TASK_STATUS_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <label>
        名称关键字
        <input
          :value="keywordFilter"
          type="search"
          data-testid="task-keyword-filter"
          placeholder="按 entry_path 或文件名过滤"
          @input="$emit('update:keywordFilter', ($event.target as HTMLInputElement).value)"
        />
      </label>
    </header>

    <div v-if="errorMessage" class="task-table__error">{{ errorMessage }}</div>
    <div v-else-if="loading" class="task-table__empty">加载中...</div>
    <div v-else-if="tasks.length === 0" class="task-table__empty">当前没有任务</div>
    <table v-else class="task-table__table">
      <thead>
        <tr>
          <th>任务ID</th>
          <th>状态</th>
          <th>入口文件</th>
          <th>执行器</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="task in tasks" :key="task.task_id">
          <td>{{ task.task_id }}</td>
          <td>{{ task.status }}</td>
          <td>{{ task.entry_path }}</td>
          <td>{{ task.executor_key || '-' }}</td>
          <td>{{ task.created_at || '-' }}</td>
          <td class="task-table__actions">
            <button
              type="button"
              :data-testid="`task-open-${task.task_id}`"
              @click="$emit('open-task', task.task_id)"
            >
              详情
            </button>
            <button
              v-if="cancellableStatuses.includes(task.status)"
              type="button"
              :data-testid="`task-cancel-${task.task_id}`"
              @click="$emit('cancel-task', task.task_id)"
            >
              取消
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { TASK_STATUS_OPTIONS, type TaskListItem } from '@/modules/my/types/tasks'

defineProps<{
  tasks: TaskListItem[]
  loading: boolean
  errorMessage: string
  statusFilter: string
  keywordFilter: string
}>()

defineEmits<{
  'update:statusFilter': [value: string]
  'update:keywordFilter': [value: string]
  'open-task': [taskId: string]
  'cancel-task': [taskId: string]
}>()

const cancellableStatuses = ['queued', 'submitted', 'assigned', 'preparing', 'running', 'uploading']
</script>

<style scoped>
.task-table {
  display: grid;
  gap: 16px;
}

.task-table__filters {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.task-table__filters label {
  display: grid;
  gap: 6px;
  color: #334155;
}

.task-table__table {
  width: 100%;
  border-collapse: collapse;
}

.task-table__table th,
.task-table__table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
}

.task-table__actions {
  display: flex;
  gap: 8px;
}

.task-table__empty,
.task-table__error {
  padding: 24px;
  border-radius: 14px;
  background: #f8fafc;
  color: #64748b;
}

.task-table__error {
  background: #fef2f2;
  color: #b91c1c;
}

button,
select,
input {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 8px 12px;
  background: #fff;
}
</style>
