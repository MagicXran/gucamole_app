import http from '@/services/http'

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
