import http from '@/services/http'

import type { AdminAppFormPayload, AdminAppRecord, AdminPoolRecord, PoolAttachments } from '@/modules/admin/types/apps'

export function listAdminApps() {
  return http.get<AdminAppRecord[]>('/api/admin/apps')
}

export function createAdminApp(payload: AdminAppFormPayload) {
  return http.post<AdminAppRecord>('/api/admin/apps', payload)
}

export function updateAdminApp(appId: number, payload: Partial<AdminAppFormPayload>) {
  return http.put<AdminAppRecord>(`/api/admin/apps/${appId}`, payload)
}

export function deleteAdminApp(appId: number) {
  return http.delete(`/api/admin/apps/${appId}`)
}

export function listAdminPools() {
  return http.get<AdminPoolRecord[]>('/api/admin/pools')
}

export function getAdminPoolAttachments(poolId: number) {
  return http.get<PoolAttachments>(`/api/admin/pools/${poolId}/attachments`)
}

export function replaceAdminPoolAttachments(poolId: number, payload: PoolAttachments) {
  return http.put<PoolAttachments>(`/api/admin/pools/${poolId}/attachments`, payload)
}
