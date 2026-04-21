import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSessionStore } from '@/stores/session'

vi.mock('@/modules/admin/services/api/access', () => ({
  getAdminUserAcl: vi.fn(),
  listAdminUsers: vi.fn(),
  updateAdminUserAcl: vi.fn(),
}))

vi.mock('@/modules/admin/services/api/apps', () => ({
  listAdminApps: vi.fn(),
}))

const accessApi = await import('@/modules/admin/services/api/access')
const appsApi = await import('@/modules/admin/services/api/apps')

describe('AdminAclView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders the legacy user-app matrix and saves checked app ids per active user', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: { user_id: 1, username: 'admin', display_name: '管理员', is_admin: true },
    })

    vi.mocked(accessApi.listAdminUsers).mockResolvedValue({
      data: [
        {
          id: 1,
          username: 'alice',
          display_name: 'Alice',
          department: '',
          is_admin: false,
          is_active: true,
          quota_bytes: null,
          used_bytes: 0,
          used_display: '0 B',
          quota_display: '10 GB',
        },
        {
          id: 2,
          username: 'bob',
          display_name: 'Bob',
          department: '',
          is_admin: false,
          is_active: false,
          quota_bytes: null,
          used_bytes: 0,
          used_display: '0 B',
          quota_display: '10 GB',
        },
      ],
      headers: {},
    } as never)
    vi.mocked(appsApi.listAdminApps).mockResolvedValue({
      data: [
        {
          id: 11,
          name: 'Fluent',
          icon: 'desktop',
          app_kind: 'commercial_software',
          protocol: 'rdp',
          hostname: 'rdp.local',
          port: 3389,
          rdp_username: null,
          rdp_password: null,
          domain: null,
          security: null,
          ignore_cert: true,
          remote_app: 'fluent.exe',
          remote_app_dir: null,
          remote_app_args: null,
          color_depth: null,
          disable_gfx: true,
          resize_method: 'display-update',
          enable_wallpaper: false,
          enable_font_smoothing: true,
          disable_copy: false,
          disable_paste: false,
          enable_audio: true,
          enable_audio_input: false,
          enable_printing: false,
          disable_download: null,
          disable_upload: null,
          timezone: null,
          keyboard_layout: null,
          pool_id: null,
          member_max_concurrent: 1,
          is_active: true,
          script_enabled: false,
          script_profile_key: null,
          script_profile_name: null,
          script_executor_key: null,
          script_worker_group_id: null,
          script_scratch_root: null,
          script_python_executable: null,
          script_python_env: null,
        },
        {
          id: 12,
          name: 'OldDisabledApp',
          icon: 'desktop',
          app_kind: 'commercial_software',
          protocol: 'rdp',
          hostname: 'rdp.local',
          port: 3389,
          rdp_username: null,
          rdp_password: null,
          domain: null,
          security: null,
          ignore_cert: true,
          remote_app: 'old.exe',
          remote_app_dir: null,
          remote_app_args: null,
          color_depth: null,
          disable_gfx: true,
          resize_method: 'display-update',
          enable_wallpaper: false,
          enable_font_smoothing: true,
          disable_copy: false,
          disable_paste: false,
          enable_audio: true,
          enable_audio_input: false,
          enable_printing: false,
          disable_download: null,
          disable_upload: null,
          timezone: null,
          keyboard_layout: null,
          pool_id: null,
          member_max_concurrent: 1,
          is_active: false,
          script_enabled: false,
          script_profile_key: null,
          script_profile_name: null,
          script_executor_key: null,
          script_worker_group_id: null,
          script_scratch_root: null,
          script_python_executable: null,
          script_python_env: null,
        },
      ],
      headers: {},
    } as never)
    vi.mocked(accessApi.getAdminUserAcl).mockResolvedValue({
      data: { user_id: 1, app_ids: [11] },
      headers: {},
    } as never)
    vi.mocked(accessApi.updateAdminUserAcl).mockResolvedValue({
      data: { user_id: 1, app_ids: [11] },
      headers: {},
    } as never)

    const { default: AdminAclView } = await import('@/modules/admin/views/AdminAclView.vue')
    const wrapper = mount(AdminAclView)
    await flushPromises()

    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Fluent')
    expect(wrapper.text()).not.toContain('Bob')
    expect(wrapper.text()).not.toContain('OldDisabledApp')

    expect((wrapper.get('[data-testid="admin-acl-user-1-app-11"]').element as HTMLInputElement).checked).toBe(true)

    await wrapper.get('[data-testid="admin-acl-user-1-app-11"]').setValue(false)
    await wrapper.get('[data-testid="admin-acl-save"]').trigger('click')
    await flushPromises()

    expect(accessApi.updateAdminUserAcl).toHaveBeenCalledWith(1, { app_ids: [] })
  })
})
