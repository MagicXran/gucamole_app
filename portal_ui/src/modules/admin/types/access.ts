export type AdminUserRecord = {
  id: number
  username: string
  display_name: string
  department: string
  is_admin: boolean
  is_active: boolean
  quota_bytes: number | null
  used_bytes: number
  used_display: string
  quota_display: string
}

export type AdminUserCreatePayload = {
  username: string
  password: string
  display_name: string
  is_admin: boolean
  quota_gb: number
}

export type AdminUserUpdatePayload = {
  display_name?: string
  password?: string
  is_admin?: boolean
  is_active?: boolean
  quota_gb?: number
}

export type AdminUserAclResponse = {
  user_id: number
  app_ids: number[]
}

export type AdminUserAclUpdatePayload = {
  app_ids: number[]
}
