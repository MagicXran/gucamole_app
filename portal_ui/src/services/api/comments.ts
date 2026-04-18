import http from '@/services/http'
import type { CommentCreateRequest, CommentItem, CommentTargetType } from '@/types/comments'

export function listComments(targetType: CommentTargetType, targetId: number) {
  return http.get<CommentItem[]>('/api/comments', {
    params: {
      target_type: targetType,
      target_id: targetId,
    },
  })
}

export function createComment(payload: CommentCreateRequest) {
  return http.post<CommentItem>('/api/comments', payload)
}
