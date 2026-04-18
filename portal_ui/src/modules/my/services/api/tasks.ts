import http from '@/services/http'
import type { TaskArtifactItem, TaskDetail, TaskListItem, TaskLogItem } from '@/modules/my/types/tasks'

export function listTasks() {
  return http.get<TaskListItem[]>('/api/tasks')
}

export function getTask(taskId: string) {
  return http.get<TaskDetail>(`/api/tasks/${encodeURIComponent(taskId)}`)
}

export function getTaskLogs(taskId: string) {
  return http.get<{ items: TaskLogItem[] }>(`/api/tasks/${encodeURIComponent(taskId)}/logs`)
}

export function getTaskArtifacts(taskId: string) {
  return http.get<{ items: TaskArtifactItem[] }>(`/api/tasks/${encodeURIComponent(taskId)}/artifacts`)
}

export function cancelTask(taskId: string) {
  return http.post<TaskDetail>(`/api/tasks/${encodeURIComponent(taskId)}/cancel`)
}
