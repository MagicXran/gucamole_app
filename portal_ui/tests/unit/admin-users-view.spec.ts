import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSessionStore } from '@/stores/session'

vi.mock('@/modules/admin/services/api/access', () => ({
  createAdminUser: vi.fn(),
  deleteAdminUser: vi.fn(),
  listAdminUsers: vi.fn(),
  updateAdminUser: vi.fn(),
}))

const accessApi = await import('@/modules/admin/services/api/access')

describe('AdminUsersView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders legacy user controls and updates user payload without forcing password change', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: { user_id: 1, username: 'admin', display_name: '管理员', is_admin: true },
    })

    vi.mocked(accessApi.listAdminUsers).mockResolvedValue({
      data: [
        {
          id: 1,
          username: 'admin',
          display_name: '管理员',
          department: '',
          is_admin: true,
          is_active: true,
          quota_bytes: 10737418240,
          used_bytes: 1073741824,
          used_display: '1 GB',
          quota_display: '10 GB',
        },
      ],
      headers: {},
    } as never)
    vi.mocked(accessApi.updateAdminUser).mockResolvedValue({
      data: {
        id: 1,
        username: 'admin',
        display_name: '管理员-新',
        department: '',
        is_admin: false,
        is_active: false,
      },
      headers: {},
    } as never)

    const { default: AdminUsersView } = await import('@/modules/admin/views/AdminUsersView.vue')
    const wrapper = mount(AdminUsersView)
    await flushPromises()

    expect(wrapper.text()).toContain('管理员')
    expect(wrapper.text()).toContain('1 GB / 10 GB')

    await wrapper.get('[data-testid="admin-user-edit-1"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="admin-user-display"]').setValue('管理员-新')
    await wrapper.get('[data-testid="admin-user-quota"]').setValue('20 GB')
    await wrapper.get('[data-testid="admin-user-is-admin"]').setValue(false)
    await wrapper.get('[data-testid="admin-user-is-active"]').setValue(false)
    await wrapper.get('[data-testid="admin-user-submit"]').trigger('click')
    await flushPromises()

    expect(accessApi.updateAdminUser).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        display_name: '管理员-新',
        quota_gb: 20,
        is_admin: false,
        is_active: false,
      }),
    )
    expect(accessApi.updateAdminUser).not.toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        password: expect.any(String),
      }),
    )
  })
})
