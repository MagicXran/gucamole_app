export type AppKind = 'commercial_software' | 'simulation_app' | 'compute_tool'

export type AdminAppRecord = {
  id: number
  name: string
  icon: string
  protocol: string
  hostname: string
  port: number
  remote_app: string | null
  pool_id: number | null
  member_max_concurrent: number
  app_kind: AppKind
  is_active: boolean
}

export type AdminAppFormPayload = {
  name: string
  icon: string
  protocol: string
  hostname: string
  port: number
  remote_app: string
  pool_id: number | null
  member_max_concurrent: number
  app_kind: AppKind
  ignore_cert: boolean
  is_active: boolean
}

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

export type AttachmentGroupKey = 'tutorial_docs' | 'video_resources' | 'plugin_downloads'

export type AttachmentItemDraft = {
  title: string
  summary: string
  link_url: string
  sort_order: number
}

export type PoolAttachments = {
  pool_id: number
  tutorial_docs: AttachmentItemDraft[]
  video_resources: AttachmentItemDraft[]
  plugin_downloads: AttachmentItemDraft[]
}
