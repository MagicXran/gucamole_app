export type ComputeAppCard = {
  id: number
  pool_id: number
  app_kind?: 'commercial_software' | 'simulation_app' | 'compute_tool'
  name: string
  icon: string
  protocol: string
  supports_gui: boolean
  supports_script: boolean
  script_runtime_id: number | null
  script_profile_key: string | null
  script_profile_name: string | null
  script_schedulable: boolean
  script_status_code: string
  script_status_label: string
  script_status_tone: string
  script_status_summary: string
  script_status_reason: string
  resource_status_code: string
  resource_status_label: string
  resource_status_tone: string
  active_count: number
  queued_count: number
  max_concurrent: number
  has_capacity: boolean
}

export type AppAttachmentItem = {
  id: number
  title: string
  summary: string
  link_url: string
  sort_order: number
}

export type PoolAttachmentResponse = {
  pool_id: number
  tutorial_docs: AppAttachmentItem[]
  video_resources: AppAttachmentItem[]
  plugin_downloads: AppAttachmentItem[]
}
