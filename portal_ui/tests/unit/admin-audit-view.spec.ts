import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSessionStore } from '@/stores/session'

vi.mock('@/modules/admin/services/api/audit', () => ({
  getAdminAuditLogs: vi.fn(),
}))

const auditApi = await import('@/modules/admin/services/api/audit')

describe('AdminAuditView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('loads audit logs with filters and paginates results', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: { user_id: 1, username: 'admin', display_name: '管理员', is_admin: true },
    })

    vi.mocked(auditApi.getAdminAuditLogs)
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 1,
              user_id: 1,
              username: 'admin',
              action: 'admin_create_app',
              target_name: 'Fluent',
              ip_address: '127.0.0.1',
              detail: 'created',
              created_at: '2026-04-21 10:00:00',
            },
          ],
          total: 25,
          page: 1,
          page_size: 20,
        },
        headers: {},
      } as never)
      .mockResolvedValueOnce({
        data: {
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
        },
        headers: {},
      } as never)

    const { default: AdminAuditView } = await import('@/modules/admin/views/AdminAuditView.vue')
    const wrapper = mount(AdminAuditView)
    await flushPromises()

    expect(wrapper.text()).toContain('Fluent')
    expect(wrapper.text()).toContain('第 1 / 2 页')

    await wrapper.get('[data-testid="audit-filter-username"]').setValue('alice')
    await wrapper.get('[data-testid="audit-filter-action"]').setValue('launch_app')
    await wrapper.get('[data-testid="audit-filter-start"]').setValue('2026-04-20')
    await wrapper.get('[data-testid="audit-filter-end"]').setValue('2026-04-21')
    await wrapper.get('[data-testid="audit-filter-submit"]').trigger('click')
    await flushPromises()

    expect(auditApi.getAdminAuditLogs).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 20,
      username: 'alice',
      action: 'launch_app',
      date_start: '2026-04-20',
      date_end: '2026-04-21',
    })
  })
})
