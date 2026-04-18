import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  cancelTask as cancelTaskRequest,
  getTask,
  getTaskArtifacts,
  getTaskLogs,
  listTasks,
} from '@/modules/my/services/api/tasks'
import type { TaskArtifactItem, TaskDetail, TaskListItem, TaskLogItem } from '@/modules/my/types/tasks'

function resolveErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

function keywordMatches(task: TaskListItem, keyword: string) {
  if (!keyword) {
    return true
  }

  const fullPath = String(task.entry_path || '').toLowerCase()
  const fileName = fullPath.split('/').pop() || ''
  return fullPath.includes(keyword) || fileName.includes(keyword)
}

function updateTaskInList(tasks: TaskListItem[], nextTask: TaskDetail) {
  return tasks.map((task) => (task.task_id === nextTask.task_id ? { ...task, ...nextTask } : task))
}

export const useTasksStore = defineStore('my-tasks', () => {
  const tasks = ref<TaskListItem[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const errorMessage = ref('')
  const statusFilter = ref('all')
  const keywordFilter = ref('')

  const drawerOpen = ref(false)
  const detailLoading = ref(false)
  const detailErrorMessage = ref('')
  const cancelLoading = ref(false)
  const selectedTaskId = ref('')
  const detailTask = ref<TaskDetail | null>(null)
  const logs = ref<TaskLogItem[]>([])
  const artifacts = ref<TaskArtifactItem[]>([])

  const filteredTasks = computed(() => {
    const status = statusFilter.value.trim().toLowerCase()
    const keyword = keywordFilter.value.trim().toLowerCase()

    return tasks.value.filter((task) => {
      if (status && status !== 'all' && String(task.status).toLowerCase() !== status) {
        return false
      }
      return keywordMatches(task, keyword)
    })
  })

  async function loadTasks() {
    loading.value = true
    errorMessage.value = ''

    try {
      const response = await listTasks()
      tasks.value = response.data
    } catch (error) {
      tasks.value = []
      errorMessage.value = resolveErrorMessage(error, '加载任务失败')
    } finally {
      loaded.value = true
      loading.value = false
    }
  }

  async function openTask(taskId: string) {
    drawerOpen.value = true
    selectedTaskId.value = taskId
    detailLoading.value = true
    detailErrorMessage.value = ''
    logs.value = []
    artifacts.value = []

    try {
      const taskResponse = await getTask(taskId)
      detailTask.value = taskResponse.data
      tasks.value = updateTaskInList(tasks.value, taskResponse.data)

      const [logsResult, artifactsResult] = await Promise.allSettled([
        getTaskLogs(taskId),
        getTaskArtifacts(taskId),
      ])

      if (logsResult.status === 'fulfilled') {
        logs.value = logsResult.value.data.items || []
      } else {
        logs.value = []
      }

      if (artifactsResult.status === 'fulfilled') {
        artifacts.value = artifactsResult.value.data.items || []
      } else {
        artifacts.value = []
      }

      const sideErrors: string[] = []
      if (logsResult.status === 'rejected') {
        sideErrors.push(resolveErrorMessage(logsResult.reason, '加载任务日志失败'))
      }
      if (artifactsResult.status === 'rejected') {
        sideErrors.push(resolveErrorMessage(artifactsResult.reason, '加载任务结果失败'))
      }
      if (sideErrors.length > 0) {
        detailErrorMessage.value = sideErrors.join('；')
      }
    } catch (error) {
      detailTask.value = null
      logs.value = []
      artifacts.value = []
      detailErrorMessage.value = resolveErrorMessage(error, '加载任务详情失败')
    } finally {
      detailLoading.value = false
    }
  }

  function closeDrawer() {
    drawerOpen.value = false
  }

  async function cancelSelectedTask(taskId?: string) {
    const targetTaskId = taskId || selectedTaskId.value
    if (!targetTaskId) {
      return
    }

    cancelLoading.value = true
    detailErrorMessage.value = ''

    try {
      const response = await cancelTaskRequest(targetTaskId)
      detailTask.value = { ...(detailTask.value || {}), ...response.data } as TaskDetail
      tasks.value = updateTaskInList(tasks.value, response.data)
    } catch (error) {
      detailErrorMessage.value = resolveErrorMessage(error, '取消任务失败')
    } finally {
      cancelLoading.value = false
    }
  }

  return {
    tasks,
    loading,
    loaded,
    errorMessage,
    statusFilter,
    keywordFilter,
    filteredTasks,
    drawerOpen,
    detailLoading,
    detailErrorMessage,
    cancelLoading,
    detailTask,
    logs,
    artifacts,
    loadTasks,
    openTask,
    closeDrawer,
    cancelSelectedTask,
  }
})
