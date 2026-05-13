import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSessionStore } from '@/stores/session'

vi.mock('@/modules/admin/services/api/pools', () => ({
  createAdminPool: vi.fn(),
  getAdminPoolAttachments: vi.fn(),
  listAdminPools: vi.fn(),
  replaceAdminPoolAttachments: vi.fn(),
  updateAdminPool: vi.fn(),
}))

const poolsApi = await import('@/modules/admin/services/api/pools')

describe('AdminPoolsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders pool rows and updates a resource pool payload', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: { user_id: 1, username: 'admin', display_name: '管理员', is_admin: true },
    })

    vi.mocked(poolsApi.listAdminPools).mockResolvedValue({
      data: [
        {
          id: 7,
          name: '求解池',
          icon: 'desktop',
          max_concurrent: 2,
          auto_dispatch_enabled: true,
          dispatch_grace_seconds: 120,
          stale_timeout_seconds: 180,
          idle_timeout_seconds: 600,
          is_active: true,
          active_count: 1,
          queued_count: 2,
        },
      ],
      headers: {},
    } as never)
    vi.mocked(poolsApi.updateAdminPool).mockResolvedValue({
      data: {
        id: 7,
        name: '求解池-新',
        icon: 'desktop',
        max_concurrent: 4,
        auto_dispatch_enabled: false,
        dispatch_grace_seconds: 60,
        stale_timeout_seconds: 240,
        idle_timeout_seconds: 900,
        is_active: false,
        active_count: 1,
        queued_count: 2,
      },
      headers: {},
    } as never)
    vi.mocked(poolsApi.getAdminPoolAttachments).mockResolvedValue({
      data: {
        pool_id: 7,
        tutorial_docs: [{ title: '求解说明', summary: '', link_url: 'https://example/doc', sort_order: 0 }],
        video_resources: [],
        plugin_downloads: [],
      },
      headers: {},
    } as never)
    vi.mocked(poolsApi.replaceAdminPoolAttachments).mockResolvedValue({
      data: {
        pool_id: 7,
        tutorial_docs: [{ title: '求解说明-新', summary: '', link_url: 'https://example/new-doc', sort_order: 0 }],
        video_resources: [],
        plugin_downloads: [],
      },
      headers: {},
    } as never)

    const { default: AdminPoolsView } = await import('@/modules/admin/views/AdminPoolsView.vue')
    const wrapper = mount(AdminPoolsView)
    await flushPromises()

    expect(wrapper.text()).toContain('求解池')
    expect(wrapper.text()).toContain('1')
    expect(wrapper.text()).toContain('2')

    await wrapper.get('[data-testid="admin-pool-edit-7"]').trigger('click')
    await flushPromises()
    expect(poolsApi.getAdminPoolAttachments).toHaveBeenCalledWith(7)
    await wrapper.get('[data-testid="admin-pool-name"]').setValue('求解池-新')
    await wrapper.get('[data-testid="admin-pool-max"]').setValue('4')
    await wrapper.get('[data-testid="admin-pool-grace"]').setValue('60')
    await wrapper.get('[data-testid="admin-pool-stale"]').setValue('240')
    await wrapper.get('[data-testid="admin-pool-idle"]').setValue('900')
    await wrapper.get('[data-testid="admin-pool-auto"]').setValue(false)
    await wrapper.get('[data-testid="admin-pool-active"]').setValue(false)
    await wrapper.get('[data-testid="attachment-title-tutorial_docs-0"]').setValue('求解说明-新')
    await wrapper.get('[data-testid="attachment-link-tutorial_docs-0"]').setValue('https://example/new-doc')
    await wrapper.get('[data-testid="admin-pool-submit"]').trigger('click')
    await flushPromises()

    expect(poolsApi.updateAdminPool).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        name: '求解池-新',
        max_concurrent: 4,
        auto_dispatch_enabled: false,
        dispatch_grace_seconds: 60,
        stale_timeout_seconds: 240,
        idle_timeout_seconds: 900,
        is_active: false,
      }),
    )
    expect(poolsApi.replaceAdminPoolAttachments).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        tutorial_docs: [
          expect.objectContaining({
            title: '求解说明-新',
            link_url: 'https://example/new-doc',
          }),
        ],
      }),
    )
  })
})
