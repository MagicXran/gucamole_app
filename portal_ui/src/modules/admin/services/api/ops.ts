import http from '@/services/http'

import type {
  AdminMonitorOverview,
  AdminMonitorSessionsResponse,
  AdminQueueListResponse,
  AdminWorkerEnrollmentResponse,
  AdminWorkerGroupCreatePayload,
  AdminWorkerGroupsResponse,
  AdminWorkerNodeCreatePayload,
  AdminWorkerNodesResponse,
  AdminWorkerRevokeResponse,
  AdminWorkerTokenResponse,
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

export function createAdminWorkerGroup(payload: AdminWorkerGroupCreatePayload) {
  return http.post('/api/admin/workers/groups', payload)
}

export function listAdminWorkerNodes() {
  return http.get<AdminWorkerNodesResponse>('/api/admin/workers/nodes')
}

export function createAdminWorkerNode(payload: AdminWorkerNodeCreatePayload) {
  return http.post('/api/admin/workers/nodes', payload)
}

export function issueAdminWorkerEnrollment(workerNodeId: number, payload = { expires_hours: 24 }) {
  return http.post<AdminWorkerEnrollmentResponse>(`/api/admin/workers/nodes/${workerNodeId}/enrollment`, payload)
}

export function rotateAdminWorkerToken(workerNodeId: number) {
  return http.post<AdminWorkerTokenResponse>(`/api/admin/workers/nodes/${workerNodeId}/rotate-token`)
}

export function revokeAdminWorkerNode(workerNodeId: number) {
  return http.post<AdminWorkerRevokeResponse>(`/api/admin/workers/nodes/${workerNodeId}/revoke`)
}
