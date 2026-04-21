import http from '@/services/http'

import type { AdminAuditLogQuery, AdminAuditLogResponse } from '@/modules/admin/types/audit'

export function getAdminAuditLogs(query: AdminAuditLogQuery) {
  return http.get<AdminAuditLogResponse>('/api/admin/audit-logs', { params: query })
}
