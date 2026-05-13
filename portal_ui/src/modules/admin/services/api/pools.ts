import http from '@/services/http'

import type { PoolAttachments } from '@/modules/admin/types/apps'
import type { AdminPoolPayload, AdminPoolRecord } from '@/modules/admin/types/pools'

export function listAdminPools() {
  return http.get<AdminPoolRecord[]>('/api/admin/pools')
}

export function createAdminPool(payload: AdminPoolPayload) {
  return http.post<AdminPoolRecord>('/api/admin/pools', payload)
}

export function updateAdminPool(poolId: number, payload: Partial<AdminPoolPayload>) {
  return http.put<AdminPoolRecord>(`/api/admin/pools/${poolId}`, payload)
}

export function getAdminPoolAttachments(poolId: number) {
  return http.get<PoolAttachments>(`/api/admin/pools/${poolId}/attachments`)
}

export function replaceAdminPoolAttachments(poolId: number, payload: PoolAttachments) {
  return http.put<PoolAttachments>(`/api/admin/pools/${poolId}/attachments`, payload)
}
