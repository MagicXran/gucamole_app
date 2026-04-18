import http from '@/services/http'
import type { ComputeAppCard, PoolAttachmentResponse } from '@/types/compute'

export function listRemoteApps() {
  return http.get<ComputeAppCard[]>('/api/remote-apps/')
}

export function getPoolAttachments(poolId: number) {
  return http.get<PoolAttachmentResponse>(`/api/app-attachments/pools/${poolId}`)
}
