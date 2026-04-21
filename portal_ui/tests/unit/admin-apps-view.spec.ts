import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSessionStore } from '@/stores/session'

vi.mock('@/modules/admin/services/api/apps', () => ({
  createAdminApp: vi.fn(),
  deleteAdminApp: vi.fn(),
  getAdminPoolAttachments: vi.fn(),
  listAdminApps: vi.fn(),
  listAdminPools: vi.fn(),
  listAdminScriptProfiles: vi.fn(),
  listAdminWorkerGroups: vi.fn(),
  replaceAdminPoolAttachments: vi.fn(),
  updateAdminApp: vi.fn(),
}))

const appsApi = await import('@/modules/admin/services/api/apps')

describe('AdminAppsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('loads apps, edits app_kind, and saves pool attachments through the Vue admin workbench', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: {
        user_id: 1,
        username: 'admin',
        display_name: '管理员',
        is_admin: true,
      },
    })

    vi.mocked(appsApi.listAdminApps).mockResolvedValue({
      data: [
        {
          id: 9,
          name: 'Fluent',
          icon: 'desktop',
          protocol: 'rdp',
          hostname: 'rdp.example.local',
          port: 3389,
          remote_app: 'fluent.exe',
          pool_id: 7,
          member_max_concurrent: 1,
          app_kind: 'commercial_software',
          is_active: true,
        },
      ],
      headers: {},
    } as never)
    vi.mocked(appsApi.listAdminPools).mockResolvedValue({
      data: [
        {
          id: 7,
          name: 'Fluent共享池',
          icon: 'desktop',
          max_concurrent: 2,
          auto_dispatch_enabled: true,
          dispatch_grace_seconds: 120,
          stale_timeout_seconds: 120,
          idle_timeout_seconds: null,
          is_active: true,
          active_count: 0,
          queued_count: 0,
        },
      ],
      headers: {},
    } as never)
    vi.mocked(appsApi.getAdminPoolAttachments).mockResolvedValue({
      data: {
        pool_id: 7,
        tutorial_docs: [{ title: '用户手册', summary: 'PDF', link_url: 'https://example/doc', sort_order: 0 }],
        video_resources: [],
        plugin_downloads: [],
      },
      headers: {},
    } as never)
    vi.mocked(appsApi.updateAdminApp).mockResolvedValue({
      data: {
        id: 9,
        name: 'Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        hostname: 'rdp.example.local',
        port: 3389,
        remote_app: 'fluent.exe',
        pool_id: 7,
        member_max_concurrent: 1,
        app_kind: 'simulation_app',
        is_active: true,
      },
      headers: {},
    } as never)
    vi.mocked(appsApi.replaceAdminPoolAttachments).mockResolvedValue({
      data: {
        pool_id: 7,
        tutorial_docs: [{ title: '新版手册', summary: '', link_url: 'https://example/new-doc', sort_order: 0 }],
        video_resources: [],
        plugin_downloads: [],
      },
      headers: {},
    } as never)

    const { default: AdminAppsView } = await import('@/modules/admin/views/AdminAppsView.vue')
    const wrapper = mount(AdminAppsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Fluent')

    await wrapper.get('[data-testid="admin-app-edit-9"]').trigger('click')
    await flushPromises()

    expect(appsApi.getAdminPoolAttachments).toHaveBeenCalledWith(7)
    expect((wrapper.get('[data-testid="admin-app-kind"]').element as HTMLSelectElement).value).toBe('commercial_software')

    await wrapper.get('[data-testid="admin-app-kind"]').setValue('simulation_app')
    await wrapper.get('[data-testid="attachment-title-tutorial_docs-0"]').setValue('新版手册')
    await wrapper.get('[data-testid="attachment-link-tutorial_docs-0"]').setValue('https://example/new-doc')
    await wrapper.get('[data-testid="admin-app-submit"]').trigger('click')
    await flushPromises()

    expect(appsApi.updateAdminApp).toHaveBeenCalledWith(
      9,
      expect.objectContaining({
        app_kind: 'simulation_app',
      }),
    )
    expect(appsApi.replaceAdminPoolAttachments).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        tutorial_docs: [
          expect.objectContaining({
            title: '新版手册',
            link_url: 'https://example/new-doc',
          }),
        ],
      }),
    )
  })

  it('keeps existing pool attachments bound to the original pool when editing app pool selection', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: {
        user_id: 1,
        username: 'admin',
        display_name: '管理员',
        is_admin: true,
      },
    })

    vi.mocked(appsApi.listAdminApps).mockResolvedValue({
      data: [
        {
          id: 9,
          name: 'Fluent',
          icon: 'desktop',
          protocol: 'rdp',
          hostname: 'rdp.example.local',
          port: 3389,
          remote_app: 'fluent.exe',
          pool_id: 7,
          member_max_concurrent: 1,
          app_kind: 'commercial_software',
          is_active: true,
        },
      ],
      headers: {},
    } as never)
    vi.mocked(appsApi.listAdminPools).mockResolvedValue({
      data: [
        {
          id: 7,
          name: '原始资源池',
          icon: 'desktop',
          max_concurrent: 2,
          auto_dispatch_enabled: true,
          dispatch_grace_seconds: 120,
          stale_timeout_seconds: 120,
          idle_timeout_seconds: null,
          is_active: true,
          active_count: 0,
          queued_count: 0,
        },
        {
          id: 11,
          name: '新资源池',
          icon: 'desktop',
          max_concurrent: 2,
          auto_dispatch_enabled: true,
          dispatch_grace_seconds: 120,
          stale_timeout_seconds: 120,
          idle_timeout_seconds: null,
          is_active: true,
          active_count: 0,
          queued_count: 0,
        },
      ],
      headers: {},
    } as never)
    vi.mocked(appsApi.getAdminPoolAttachments).mockResolvedValue({
      data: {
        pool_id: 7,
        tutorial_docs: [{ title: '原始手册', summary: '', link_url: 'https://example/original', sort_order: 0 }],
        video_resources: [],
        plugin_downloads: [],
      },
      headers: {},
    } as never)
    vi.mocked(appsApi.updateAdminApp).mockResolvedValue({
      data: {
        id: 9,
        name: 'Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        hostname: 'rdp.example.local',
        port: 3389,
        remote_app: 'fluent.exe',
        pool_id: 11,
        member_max_concurrent: 1,
        app_kind: 'commercial_software',
        is_active: true,
      },
      headers: {},
    } as never)
    vi.mocked(appsApi.replaceAdminPoolAttachments).mockResolvedValue({
      data: {
        pool_id: 7,
        tutorial_docs: [{ title: '改过的手册', summary: '', link_url: 'https://example/changed', sort_order: 0 }],
        video_resources: [],
        plugin_downloads: [],
      },
      headers: {},
    } as never)

    const { default: AdminAppsView } = await import('@/modules/admin/views/AdminAppsView.vue')
    const wrapper = mount(AdminAppsView)
    await flushPromises()

    await wrapper.get('[data-testid="admin-app-edit-9"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="admin-app-pool"]').setValue('11')
    await flushPromises()

    expect(wrapper.text()).toMatch(/仍绑定原资源池|保存 App 后再改/)
    expect(appsApi.getAdminPoolAttachments).toHaveBeenCalledTimes(1)
    expect(appsApi.getAdminPoolAttachments).toHaveBeenCalledWith(7)

    await wrapper.get('[data-testid="attachment-title-tutorial_docs-0"]').setValue('改过的手册')
    await wrapper.get('[data-testid="attachment-link-tutorial_docs-0"]').setValue('https://example/changed')
    await wrapper.get('[data-testid="admin-app-submit"]').trigger('click')
    await flushPromises()

    expect(appsApi.updateAdminApp).toHaveBeenCalledWith(
      9,
      expect.objectContaining({
        pool_id: 11,
      }),
    )
    expect(appsApi.replaceAdminPoolAttachments).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        tutorial_docs: [expect.objectContaining({ title: '改过的手册' })],
      }),
    )
  })

  it('clips admin actions for non-admin users', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: {
        user_id: 9,
        username: 'zhangsan',
        display_name: '张三',
        is_admin: false,
      },
    })
    vi.mocked(appsApi.listAdminApps).mockResolvedValue({ data: [], headers: {} } as never)
    vi.mocked(appsApi.listAdminPools).mockResolvedValue({ data: [], headers: {} } as never)

    const { default: AdminAppsView } = await import('@/modules/admin/views/AdminAppsView.vue')
    const wrapper = mount(AdminAppsView)
    await flushPromises()

    expect(wrapper.text()).toContain('仅管理员可操作')
    expect(wrapper.find('[data-testid="admin-app-create"]').exists()).toBe(false)
  })

  it('restores legacy RDP, transfer, localization, and script parameters in the app dialog payload', async () => {
    const { default: AdminAppFormDialog } = await import('@/modules/admin/components/AdminAppFormDialog.vue')
    const wrapper = mount(AdminAppFormDialog, {
      props: {
        open: true,
        mode: 'edit',
        saving: false,
        pools: [
          {
            id: 7,
            name: 'Fluent共享池',
            icon: 'desktop',
            max_concurrent: 2,
            auto_dispatch_enabled: true,
            dispatch_grace_seconds: 120,
            stale_timeout_seconds: 120,
            idle_timeout_seconds: null,
            is_active: true,
            active_count: 0,
            queued_count: 0,
          },
        ],
        workerGroups: [
          {
            id: 3,
            group_key: 'solver',
            name: '求解节点组',
            description: '',
            node_count: 1,
            active_node_count: 1,
            is_active: true,
          },
        ],
        scriptProfiles: [
          {
            profile_key: 'ansys_mapdl',
            display_name: 'ANSYS MAPDL',
            description: 'MAPDL 脚本任务',
            executor_key: 'python_api',
            python_executable: 'C:\\Python311\\python.exe',
            python_env: { LICENSE_SERVER: '10.0.0.8' },
          },
        ],
        initialApp: {
          id: 9,
          name: 'Fluent',
          icon: 'desktop',
          protocol: 'rdp',
          app_kind: 'commercial_software',
          hostname: 'rdp.example.local',
          port: 3389,
          rdp_username: 'old-user',
          rdp_password: 'old-pass',
          domain: 'OLD',
          security: 'nla',
          ignore_cert: true,
          remote_app: 'fluent.exe',
          remote_app_dir: 'C:\\apps\\fluent',
          remote_app_args: '-driver',
          color_depth: 24,
          disable_gfx: true,
          resize_method: 'display-update',
          enable_wallpaper: false,
          enable_font_smoothing: true,
          disable_copy: false,
          disable_paste: true,
          enable_audio: true,
          enable_audio_input: false,
          enable_printing: true,
          disable_download: null,
          disable_upload: 1,
          timezone: 'Asia/Shanghai',
          keyboard_layout: 'zh-cn-qwerty',
          pool_id: 7,
          member_max_concurrent: 1,
          is_active: true,
          script_enabled: true,
          script_profile_key: 'ansys_mapdl',
          script_profile_name: 'ANSYS MAPDL',
          script_executor_key: 'python_api',
          script_worker_group_id: 3,
          script_scratch_root: 'D:\\scratch',
          script_python_executable: 'C:\\Python311\\python.exe',
          script_python_env: { LICENSE_SERVER: '10.0.0.8' },
        },
        attachments: {
          pool_id: 7,
          tutorial_docs: [],
          video_resources: [],
          plugin_downloads: [],
        },
        attachmentsLoading: false,
        attachmentBindingWarning: '',
      },
    })

    expect(wrapper.get('[data-testid="admin-app-rdp-username"]').element).toBeInstanceOf(HTMLInputElement)
    expect((wrapper.get('[data-testid="admin-app-security"]').element as HTMLSelectElement).value).toBe('nla')
    expect((wrapper.get('[data-testid="admin-app-color-depth"]').element as HTMLSelectElement).value).toBe('24')
    expect((wrapper.get('[data-testid="admin-app-disable-upload"]').element as HTMLSelectElement).value).toBe('1')
    expect((wrapper.get('[data-testid="admin-app-script-profile"]').element as HTMLSelectElement).value).toBe('ansys_mapdl')

    await wrapper.get('[data-testid="admin-app-rdp-username"]').setValue('new-user')
    await wrapper.get('[data-testid="admin-app-disable-download"]').setValue('0')
    await wrapper.get('[data-testid="admin-app-script-python-env"]').setValue('{"LICENSE_SERVER":"10.0.0.9"}')
    await wrapper.get('[data-testid="admin-app-submit"]').trigger('click')

    const submitPayload = wrapper.emitted('submit')?.[0]?.[0]
    expect(submitPayload).toMatchObject({
      appId: 9,
      payload: expect.objectContaining({
        rdp_username: 'new-user',
        rdp_password: 'old-pass',
        domain: 'OLD',
        security: 'nla',
        remote_app_dir: 'C:\\apps\\fluent',
        remote_app_args: '-driver',
        color_depth: 24,
        disable_gfx: true,
        resize_method: 'display-update',
        disable_download: 0,
        disable_upload: 1,
        timezone: 'Asia/Shanghai',
        keyboard_layout: 'zh-cn-qwerty',
        script_enabled: true,
        script_profile_key: 'ansys_mapdl',
        script_executor_key: 'python_api',
        script_worker_group_id: 3,
        script_scratch_root: 'D:\\scratch',
        script_python_executable: 'C:\\Python311\\python.exe',
        script_python_env: { LICENSE_SERVER: '10.0.0.9' },
      }),
    })
  })
})
