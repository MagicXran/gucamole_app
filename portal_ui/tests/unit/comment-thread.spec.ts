import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CommentThread from '@/components/comments/CommentThread.vue'
import * as commentsApi from '@/services/api/comments'

describe('CommentThread', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(commentsApi, 'listComments').mockResolvedValue({
      data: [
        {
          id: 1,
          target_type: 'app',
          target_id: 11,
          user_id: 8,
          author_name: '另一个用户',
          content: '已有评论',
          created_at: '2026-04-18 09:00:00',
        },
      ],
      headers: {},
    } as never)
    vi.spyOn(commentsApi, 'createComment').mockResolvedValue({
      data: {
        id: 2,
        target_type: 'app',
        target_id: 11,
        user_id: 7,
        author_name: '测试用户',
        content: '新评论',
        created_at: '2026-04-18 10:00:00',
      },
      headers: {},
    } as never)
  })

  it('loads comments for the target and creates a new top-level comment', async () => {
    const wrapper = mount(CommentThread, {
      props: {
        targetType: 'app',
        targetId: 11,
      },
    })
    await flushPromises()

    expect(commentsApi.listComments).toHaveBeenCalledWith('app', 11)
    expect(wrapper.text()).toContain('评论')
    expect(wrapper.text()).toContain('已有评论')

    await wrapper.get('[data-testid="comment-input"]').setValue('新评论')
    await wrapper.get('[data-testid="comment-submit"]').trigger('submit')
    await flushPromises()

    expect(commentsApi.createComment).toHaveBeenCalledWith({
      target_type: 'app',
      target_id: 11,
      content: '新评论',
    })
    expect(wrapper.text()).toContain('新评论')
  })

  it('does not submit blank comments', async () => {
    const wrapper = mount(CommentThread, {
      props: {
        targetType: 'case',
        targetId: 21,
      },
    })
    await flushPromises()

    await wrapper.get('[data-testid="comment-input"]').setValue('   ')
    await wrapper.get('[data-testid="comment-submit"]').trigger('submit')

    expect(commentsApi.createComment).not.toHaveBeenCalled()
  })
})
