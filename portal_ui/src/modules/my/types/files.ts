export type WorkspaceFileItem = {
  name: string
  is_dir: boolean
  size: number
  mtime: number
}

export type WorkspaceSpaceInfo = {
  used_bytes: number
  quota_bytes: number
  used_display: string
  quota_display: string
  usage_percent: number
}

export type WorkspaceListResponse = {
  path: string
  items: WorkspaceFileItem[]
}

export type DownloadTokenResponse = {
  token: string
  expires_in: number
}

export type UploadInitResponse = {
  upload_id: string
  offset: number
  chunk_size: number
}

export type UploadChunkResponse = {
  offset: number
  complete: boolean
}

export type MoveEntryPayload = {
  sourcePath: string
  targetPath: string
}
