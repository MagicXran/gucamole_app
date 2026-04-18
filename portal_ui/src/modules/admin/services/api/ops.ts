import http from '@/services/http'

import type {
  AdminMonitorOverview,
  AdminMonitorSessionsResponse,
  AdminQueueListResponse,
  AdminWorkerGroupsResponse,
  AdminWorkerNodesResponse,
} from '@/modules/admin/types/ops'

export function listAdminQueues() {
  return http.get<AdminQueueListResponse>('/api/admin/pools/queues')
}

export function cancelAdminQueue(queueId: number) {
  return http.post<{ queue_id: number; status: string }>(`/api/admin/pools/queues/${queueId}/cancel`)
}

export function getAdminMonitorOverview() {
  return http.get<AdminMonitorOverview>('/api/admin/monitor/overview')
}

export function getAdminMonitorSessions() {
  return http.get<AdminMonitorSessionsResponse>('/api/admin/monitor/sessions')
}

export function reclaimAdminSession(sessionId: string) {
  return http.post<{ session_id: string; status: string }>(`/api/admin/pools/sessions/${encodeURIComponent(sessionId)}/reclaim`)
}

export function listAdminWorkerGroups() {
  return http.get<AdminWorkerGroupsResponse>('/api/admin/workers/groups')
}

export function listAdminWorkerNodes() {
  return http.get<AdminWorkerNodesResponse>('/api/admin/workers/nodes')
}
