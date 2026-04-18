export type TaskStatus =
  | 'queued'
  | 'submitted'
  | 'assigned'
  | 'preparing'
  | 'running'
  | 'uploading'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | string

export type TaskListItem = {
  task_id: string
  status: TaskStatus
  task_kind: string
  executor_key: string | null
  entry_path: string
  created_at: string | null
  assigned_at: string | null
  started_at: string | null
  ended_at: string | null
}

export type TaskDetail = TaskListItem & {
  id?: number
  workspace_path?: string | null
  input_snapshot_path?: string | null
  scratch_path?: string | null
  cancel_requested?: number
  result_summary_json?: Record<string, unknown> | null
}

export type TaskLogItem = {
  seq_no: number
  level: string
  message: string
  created_at: string | null
}

export type TaskArtifactItem = {
  artifact_kind: string
  display_name: string
  relative_path: string | null
  minio_bucket: string | null
  minio_object_key: string | null
  external_url: string | null
  size_bytes: number | null
  created_at: string | null
}

export const TASK_STATUS_OPTIONS = [
  { value: 'all', label: '全部状态' },
  { value: 'queued', label: 'queued' },
  { value: 'submitted', label: 'submitted' },
  { value: 'assigned', label: 'assigned' },
  { value: 'preparing', label: 'preparing' },
  { value: 'running', label: 'running' },
  { value: 'uploading', label: 'uploading' },
  { value: 'succeeded', label: 'succeeded' },
  { value: 'failed', label: 'failed' },
  { value: 'cancelled', label: 'cancelled' },
] as const
