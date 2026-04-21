export type AdminAuditLog = {
  id: number
  user_id: number
  username: string
  action: string
  target_type?: string | null
  target_id?: number | null
  target_name?: string | null
  detail?: string | null
  ip_address?: string | null
  created_at?: string | null
}

export type AdminAuditLogQuery = {
  page: number
  page_size: number
  username?: string
  action?: string
  date_start?: string
  date_end?: string
}

export type AdminAuditLogResponse = {
  items: AdminAuditLog[]
  total: number
  page: number
  page_size: number
}
