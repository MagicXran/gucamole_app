import http from '@/services/http'

import type {
  AdminUserAclResponse,
  AdminUserAclUpdatePayload,
  AdminUserCreatePayload,
  AdminUserRecord,
  AdminUserUpdatePayload,
} from '@/modules/admin/types/access'

export function listAdminUsers() {
  return http.get<AdminUserRecord[]>('/api/admin/users')
}

export function createAdminUser(payload: AdminUserCreatePayload) {
  return http.post<AdminUserRecord>('/api/admin/users', payload)
}

export function updateAdminUser(userId: number, payload: AdminUserUpdatePayload) {
  return http.put<AdminUserRecord>(`/api/admin/users/${userId}`, payload)
}

export function deleteAdminUser(userId: number) {
  return http.delete(`/api/admin/users/${userId}`)
}

export function getAdminUserAcl(userId: number) {
  return http.get<AdminUserAclResponse>(`/api/admin/users/${userId}/acl`)
}

export function updateAdminUserAcl(userId: number, payload: AdminUserAclUpdatePayload) {
  return http.put<AdminUserAclResponse>(`/api/admin/users/${userId}/acl`, payload)
}
