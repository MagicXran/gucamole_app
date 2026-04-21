export type AdminPoolRecord = {
  id: number
  name: string
  icon: string
  max_concurrent: number
  auto_dispatch_enabled: boolean
  dispatch_grace_seconds: number
  stale_timeout_seconds: number
  idle_timeout_seconds: number | null
  is_active: boolean
  active_count: number
  queued_count: number
}

export type AdminPoolPayload = {
  name: string
  icon: string
  max_concurrent: number
  auto_dispatch_enabled: boolean
  dispatch_grace_seconds: number
  stale_timeout_seconds: number
  idle_timeout_seconds: number | null
  is_active: boolean
}
