import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSessionStore } from '@/stores/session'

vi.mock('@/modules/admin/services/api/ops', () => ({
  cancelAdminQueue: vi.fn(),
  getAdminMonitorOverview: vi.fn(),
  getAdminMonitorSessions: vi.fn(),
  listAdminQueues: vi.fn(),
  listAdminWorkerGroups: vi.fn(),
  listAdminWorkerNodes: vi.fn(),
  reclaimAdminSession: vi.fn(),
}))

const opsApi = await import('@/modules/admin/services/api/ops')

describe('AdminQueuesView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders queue rows and cancels a queue item', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: { user_id: 1, username: 'admin', display_name: '管理员', is_admin: true },
    })

    vi.mocked(opsApi.listAdminQueues).mockResolvedValue({
      data: {
        items: [
          {
            queue_id: 12,
            pool_name: '求解池',
            display_name: '测试员',
            status: 'queued',
            created_at: '2026-04-18 10:00:00',
            ready_expires_at: '',
            cancel_reason: '',
          },
        ],
      },
      headers: {},
    } as never)
    vi.mocked(opsApi.cancelAdminQueue).mockResolvedValue({
      data: { queue_id: 12, status: 'cancelled' },
      headers: {},
    } as never)

    const { default: AdminQueuesView } = await import('@/modules/admin/views/AdminQueuesView.vue')
    const wrapper = mount(AdminQueuesView)
    await flushPromises()

    expect(wrapper.text()).toContain('求解池')
    await wrapper.get('[data-testid="admin-queue-cancel-12"]').trigger('click')
    await flushPromises()

    expect(opsApi.cancelAdminQueue).toHaveBeenCalledWith(12)
  })
})
