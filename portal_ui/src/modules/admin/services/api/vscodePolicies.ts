import http from '@/services/http'

import type {
  VscodeControlCatalog,
  VscodeControlProfile,
  VscodeControlProfilePayload,
  VscodeControlProfilesResponse,
} from '@/modules/admin/types/vscodePolicies'

export function getVscodeControlCatalog() {
  return http.get<VscodeControlCatalog>('/api/admin/vscode-control-catalog')
}

export function listVscodeControlProfiles() {
  return http.get<VscodeControlProfilesResponse>('/api/admin/vscode-control-profiles')
}

export function getVscodeControlProfileEffective(profileId: number) {
  return http.get<VscodeControlProfile>(`/api/admin/vscode-control-profiles/${profileId}/effective`)
}

export function createVscodeControlProfile(payload: VscodeControlProfilePayload) {
  return http.post<VscodeControlProfile>('/api/admin/vscode-control-profiles', payload)
}

export function updateVscodeControlProfile(profileId: number, payload: VscodeControlProfilePayload) {
  return http.put<VscodeControlProfile>(`/api/admin/vscode-control-profiles/${profileId}`, payload)
}

export function deleteVscodeControlProfile(profileId: number) {
  return http.delete(`/api/admin/vscode-control-profiles/${profileId}`)
}
