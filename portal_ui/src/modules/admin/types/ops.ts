export type AdminQueueItem = {
  queue_id: number
  pool_name: string
  display_name: string
  status: string
  created_at: string
  ready_expires_at: string
  cancel_reason: string
}

export type AdminQueueListResponse = {
  items: AdminQueueItem[]
}

export type AdminMonitorApp = {
  app_id: number
  app_name: string
  icon: string
  active_count: number
}

export type AdminMonitorOverview = {
  total_online: number
  total_sessions: number
  apps: AdminMonitorApp[]
}

export type AdminMonitorSession = {
  session_id: string
  display_name: string
  username: string
  app_name: string
  status: string
  started_at: string
  last_heartbeat: string
  duration_seconds: number
}

export type AdminMonitorSessionsResponse = {
  sessions: AdminMonitorSession[]
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

export type AdminWorkerNode = {
  id: number
  display_name: string
  expected_hostname: string
  group_name: string
  status: string
  workspace_share: string
  scratch_root: string
  max_concurrent_tasks?: number
  software_ready_count: number
  software_total_count: number
  last_heartbeat_at?: string
  latest_enrollment_status?: string
  latest_enrollment_expires_at?: string
  last_error?: string
  software_inventory?: Record<string, AdminWorkerSoftwareItem>
}

export type AdminWorkerGroupsResponse = {
  items: AdminWorkerGroup[]
}

export type AdminWorkerNodesResponse = {
  items: AdminWorkerNode[]
}

export type AdminWorkerSoftwareItem = {
  software_name?: string
  ready?: boolean
  issues?: string[]
}

export type AdminWorkerGroupCreatePayload = {
  group_key: string
  name: string
  description: string
  max_claim_batch: number
}

export type AdminWorkerNodeCreatePayload = {
  group_id: number
  display_name: string
  expected_hostname: string
  scratch_root: string
  workspace_share: string
  max_concurrent_tasks: number
}

export type AdminWorkerEnrollmentResponse = {
  worker_node_id: number
  plain_token: string
  expires_at?: string
}

export type AdminWorkerTokenResponse = {
  worker_node_id: number
  plain_token: string
}

export type AdminWorkerRevokeResponse = {
  worker_node_id: number
  status: string
}
