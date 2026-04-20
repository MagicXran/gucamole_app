import http from '@/services/http'
import type {
  DownloadTokenResponse,
  UploadChunkResponse,
  UploadInitResponse,
  WorkspaceListResponse,
  WorkspaceSpaceInfo,
} from '@/modules/my/types/files'

export function getSpaceInfo(refresh = false) {
  return http.get<WorkspaceSpaceInfo>('/api/files/space', {
    params: { refresh },
  })
}

export function listFiles(path = '') {
  return http.get<WorkspaceListResponse>('/api/files/list', {
    params: { path },
  })
}

export function createDirectory(path: string) {
  return http.post<{ message: string }>('/api/files/mkdir', { path })
}

export function deleteFile(path: string) {
  return http.delete<{ message: string }>('/api/files/file', {
    params: { path },
  })
}

export function requestDownloadToken(path: string) {
  return http.post<DownloadTokenResponse>('/api/files/download-token', { path })
}

export function moveFile(sourcePath: string, targetPath: string) {
  return http.post<{ message: string }>('/api/files/move', {
    source_path: sourcePath,
    target_path: targetPath,
  })
}

export function uploadInit(path: string, size: number) {
  const form = new FormData()
  form.append('path', path)
  form.append('size', String(size))

  return http.post<UploadInitResponse>('/api/files/upload/init', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function uploadChunk(uploadId: string, offset: number, chunk: Blob) {
  const form = new FormData()
  form.append('upload_id', uploadId)
  form.append('offset', String(offset))
  form.append('chunk', chunk)

  return http.post<UploadChunkResponse>('/api/files/upload/chunk', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function cancelUpload(uploadId: string) {
  return http.delete<{ message: string }>(`/api/files/upload/${encodeURIComponent(uploadId)}`)
}
