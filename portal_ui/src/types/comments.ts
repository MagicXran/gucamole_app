export type CommentTargetType = 'app' | 'case'

export type CommentItem = {
  id: number
  target_type: CommentTargetType
  target_id: number
  user_id: number
  author_name: string
  content: string
  created_at: string | null
}

export type CommentCreateRequest = {
  target_type: CommentTargetType
  target_id: number
  content: string
}
