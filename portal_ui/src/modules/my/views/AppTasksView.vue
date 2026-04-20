<template>
  <section class="app-tasks-view">
    <header class="app-tasks-view__header">
      <div>
        <h1>App任务</h1>
        <p>只看你自己的脚本任务，支持筛选、详情、日志和结果索引。</p>
      </div>
      <button type="button" @click="handleRefresh">刷新</button>
    </header>

    <TaskTable
      :tasks="tasksStore.filteredTasks"
      :loading="tasksStore.loading"
      :error-message="tasksStore.errorMessage"
      :status-filter="tasksStore.statusFilter"
      :keyword-filter="tasksStore.keywordFilter"
      @update:status-filter="tasksStore.statusFilter = $event"
      @update:keyword-filter="tasksStore.keywordFilter = $event"
      @open-task="handleOpenTask"
      @cancel-task="handleCancelTask"
    />

    <TaskDetailDrawer
      :open="tasksStore.drawerOpen"
      :loading="tasksStore.detailLoading"
      :error-message="tasksStore.detailErrorMessage"
      :cancel-loading="tasksStore.cancelLoading"
      :task="tasksStore.detailTask"
      :logs="tasksStore.logs"
      :artifacts="tasksStore.artifacts"
      @close="tasksStore.closeDrawer"
      @cancel-task="handleCancelTask"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import TaskDetailDrawer from '@/modules/my/components/TaskDetailDrawer.vue'
import TaskTable from '@/modules/my/components/TaskTable.vue'
import { useTasksStore } from '@/modules/my/stores/tasks'

const tasksStore = useTasksStore()

async function handleRefresh() {
  await tasksStore.loadTasks()
}

async function handleOpenTask(taskId: string) {
  await tasksStore.openTask(taskId)
}

async function handleCancelTask(taskId: string) {
  await tasksStore.cancelSelectedTask(taskId)
}

onMounted(async () => {
  if (!tasksStore.loaded) {
    await tasksStore.loadTasks()
  }
})
</script>

<style scoped>
.app-tasks-view {
  display: grid;
  gap: 18px;
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.app-tasks-view__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
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

button {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #1e3a8a;
  padding: 8px 12px;
  cursor: pointer;
}
</style>
