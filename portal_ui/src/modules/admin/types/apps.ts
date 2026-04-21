export type AppKind = 'commercial_software' | 'simulation_app' | 'compute_tool'
export type ScriptExecutorKey = 'python_api' | 'command_statusfile'
export type TransferPolicy = 0 | 1 | null
export type ColorDepth = 8 | 16 | 24 | null

export type AdminAppRecord = {
  id: number
  name: string
  icon: string
  app_kind: AppKind
  protocol: string
  hostname: string
  port: number
  rdp_username?: string | null
  rdp_password?: string | null
  domain?: string | null
  security?: string | null
  ignore_cert?: boolean
  remote_app: string | null
  remote_app_dir?: string | null
  remote_app_args?: string | null
  color_depth?: ColorDepth
  disable_gfx?: boolean
  resize_method?: string
  enable_wallpaper?: boolean
  enable_font_smoothing?: boolean
  disable_copy?: boolean
  disable_paste?: boolean
  enable_audio?: boolean
  enable_audio_input?: boolean
  enable_printing?: boolean
  disable_download?: TransferPolicy
  disable_upload?: TransferPolicy
  timezone?: string | null
  keyboard_layout?: string | null
  pool_id: number | null
  member_max_concurrent: number
  is_active: boolean
  script_enabled?: boolean
  script_profile_key?: string | null
  script_profile_name?: string | null
  script_executor_key?: ScriptExecutorKey | null
  script_worker_group_id?: number | null
  script_scratch_root?: string | null
  script_python_executable?: string | null
  script_python_env?: Record<string, string> | null
}

export type AdminAppFormPayload = {
  name: string
  icon: string
  app_kind: AppKind
  protocol: string
  hostname: string
  port: number
  rdp_username: string
  rdp_password: string
  domain: string
  security: string
  ignore_cert: boolean
  remote_app: string
  remote_app_dir: string
  remote_app_args: string
  color_depth: ColorDepth
  disable_gfx: boolean
  resize_method: string
  enable_wallpaper: boolean
  enable_font_smoothing: boolean
  disable_copy: boolean
  disable_paste: boolean
  enable_audio: boolean
  enable_audio_input: boolean
  enable_printing: boolean
  disable_download: TransferPolicy
  disable_upload: TransferPolicy
  timezone: string | null
  keyboard_layout: string | null
  pool_id: number | null
  member_max_concurrent: number
  is_active: boolean
  script_enabled: boolean
  script_profile_key: string | null
  script_executor_key: ScriptExecutorKey | null
  script_worker_group_id: number | null
  script_scratch_root: string | null
  script_python_executable: string | null
  script_python_env: Record<string, string> | null
}

export type AdminScriptProfile = {
  profile_key: string
  adapter_key?: string
  display_name: string
  description: string
  executor_key: ScriptExecutorKey
  python_executable: string | null
  python_env: Record<string, string>
}

export type AdminScriptProfilesResponse = {
  items: AdminScriptProfile[]
}

export type AdminWorkerGroup = {
  id: number
  group_key: string
  name: string
  description: string
  node_count: number
  active_node_count: number
  is_active: boolean
}

export type AdminWorkerGroupsResponse = {
  items: AdminWorkerGroup[]
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
