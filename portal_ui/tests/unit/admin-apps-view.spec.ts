import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSessionStore } from '@/stores/session'

vi.mock('@/modules/admin/services/api/apps', () => ({
  createAdminApp: vi.fn(),
  deleteAdminApp: vi.fn(),
  listAdminApps: vi.fn(),
  listAdminPools: vi.fn(),
  listAdminScriptProfiles: vi.fn(),
  listAdminWorkerGroups: vi.fn(),
  updateAdminApp: vi.fn(),
}))

vi.mock('@/modules/admin/services/api/vscodePolicies', () => ({
  createVscodeControlProfile: vi.fn(),
  deleteVscodeControlProfile: vi.fn(),
  getVscodeControlCatalog: vi.fn(),
  getVscodeControlProfileEffective: vi.fn(),
  listVscodeControlProfiles: vi.fn(),
  updateVscodeControlProfile: vi.fn(),
}))

const appsApi = await import('@/modules/admin/services/api/apps')
const vscodePoliciesApi = await import('@/modules/admin/services/api/vscodePolicies')

describe('AdminAppsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.mocked(vscodePoliciesApi.listVscodeControlProfiles).mockResolvedValue({
      data: { items: [] },
      headers: {},
    } as never)
  })

  it('loads runtimes and saves app_kind changes through the Vue admin workbench', async () => {
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

    const { default: AdminAppsView } = await import('@/modules/admin/views/AdminAppsView.vue')
    const wrapper = mount(AdminAppsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Fluent')
    expect(wrapper.text()).toContain('容量池成员')

    await wrapper.get('[data-testid="admin-app-edit-9"]').trigger('click')
    await flushPromises()

    expect((wrapper.get('[data-testid="admin-app-kind"]').element as HTMLSelectElement).value).toBe('commercial_software')
    expect(wrapper.text()).toContain('当前用户的个人文件空间')
    expect(wrapper.text()).not.toContain('GuacDrive')

    await wrapper.get('[data-testid="admin-app-kind"]').setValue('simulation_app')
    await wrapper.get('[data-testid="admin-app-submit"]').trigger('click')
    await flushPromises()

    expect(appsApi.updateAdminApp).toHaveBeenCalledWith(
      9,
      expect.objectContaining({
        app_kind: 'simulation_app',
      }),
    )
  })

  it('allows switching runtime between standalone and capacity-pool mode without leaking pool attachment warnings', async () => {
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

    const { default: AdminAppsView } = await import('@/modules/admin/views/AdminAppsView.vue')
    const wrapper = mount(AdminAppsView)
    await flushPromises()

    await wrapper.get('[data-testid="admin-app-edit-9"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="admin-app-pool"]').setValue('')
    await flushPromises()

    expect(wrapper.text()).not.toMatch(/仍绑定原资源池|保存 App 后再改/)
    await wrapper.get('[data-testid="admin-app-submit"]').trigger('click')
    await flushPromises()

    expect(appsApi.updateAdminApp).toHaveBeenCalledWith(
      9,
      expect.objectContaining({
        pool_id: null,
      }),
    )

    await wrapper.get('[data-testid="admin-app-edit-9"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="admin-app-pool"]').setValue('11')
    await flushPromises()

    await wrapper.get('[data-testid="admin-app-submit"]').trigger('click')
    await flushPromises()

    expect(appsApi.updateAdminApp).toHaveBeenCalledWith(
      9,
      expect.objectContaining({
        pool_id: 11,
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
    expect(submitPayload).not.toHaveProperty('attachments')
  })

  it('binds restricted VSCode to a ready control profile', async () => {
    const { default: AdminAppFormDialog } = await import('@/modules/admin/components/AdminAppFormDialog.vue')
    const wrapper = mount(AdminAppFormDialog, {
      props: {
        open: true,
        mode: 'create',
        saving: false,
        pools: [],
        workerGroups: [],
        scriptProfiles: [],
        vscodeControlProfiles: [
          {
            id: 3,
            profile_key: 'default-controlled',
            display_name: '默认受控开发模式',
            description: '',
            policy_version: 1,
            revision: 2,
            is_active: true,
            valid: true,
            validation_errors: [],
            permissions: {},
            allowed_shells: [],
            allowed_tools: [],
            allowed_debuggers: [],
            allowed_extensions: [],
            allowed_network_targets: [],
            user_data_root: 'C:\\PortalProfiles',
            extensions_root: 'C:\\PortalExtensions',
            default_workspace_template: '\\\\tsclient\\{user_drive}',
          },
        ],
        initialApp: null,
      },
    })

    await wrapper.get('[data-testid="admin-app-name"]').setValue('VSCode')
    await wrapper.get('[data-testid="admin-app-hostname"]').setValue('rdp.example.local')
    await wrapper.get('[data-testid="admin-app-security-mode"]').setValue('restricted_vscode')
    await wrapper.get('[data-testid="admin-app-remote-app"]').setValue('||Visual Studio Code')
    await wrapper.get('[data-testid="admin-app-vscode-profile"]').setValue('3')
    await wrapper.get('[data-testid="admin-app-submit"]').trigger('click')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      payload: expect.objectContaining({
        security_mode: 'restricted_vscode',
        vscode_control_profile_id: 3,
      }),
    })
  })

  it('leaves new RemoteApp working directory empty for runtime user expansion', async () => {
    const { default: AdminAppFormDialog } = await import('@/modules/admin/components/AdminAppFormDialog.vue')
    const wrapper = mount(AdminAppFormDialog, {
      props: {
        open: true,
        mode: 'create',
        saving: false,
        pools: [],
        workerGroups: [],
        scriptProfiles: [],
        vscodeControlProfiles: [],
        initialApp: null,
      },
    })

    const remoteDirInput = wrapper.get('[data-testid="admin-app-remote-dir"]')
    expect((remoteDirInput.element as HTMLInputElement).value).toBe('')
    expect(remoteDirInput.attributes('placeholder')).toContain('当前用户')
  })

  it('rejects an inactive or invalid VSCode control profile before API submit', async () => {
    const { default: AdminAppFormDialog } = await import('@/modules/admin/components/AdminAppFormDialog.vue')
    const invalidProfile = {
      id: 4,
      profile_key: 'invalid-policy',
      display_name: '未就绪策略',
      description: '',
      policy_version: 1,
      revision: 1,
      is_active: false,
      valid: false,
      validation_errors: ['allowed_shells 为空'],
      permissions: {},
      allowed_shells: [],
      allowed_tools: [],
      allowed_debuggers: [],
      allowed_extensions: [],
      allowed_network_targets: [],
      user_data_root: 'C:\\PortalProfiles',
      extensions_root: 'C:\\PortalExtensions',
      default_workspace_template: '\\\\tsclient\\{user_drive}',
    }
    const wrapper = mount(AdminAppFormDialog, {
      props: {
        open: true,
        mode: 'edit',
        saving: false,
        pools: [],
        workerGroups: [],
        scriptProfiles: [],
        vscodeControlProfiles: [invalidProfile],
        initialApp: {
          id: 5,
          name: 'VSCode',
          icon: 'desktop',
          app_kind: 'commercial_software',
          protocol: 'rdp',
          hostname: 'rdp.example.local',
          port: 3389,
          remote_app: '||Visual Studio Code',
          security_mode: 'restricted_vscode',
          vscode_control_profile_id: 4,
          pool_id: null,
          member_max_concurrent: 1,
          is_active: true,
        },
      },
    })

    const option = wrapper.get('[data-testid="admin-app-vscode-profile"] option[value="4"]')
    expect((option.element as HTMLOptionElement).disabled).toBe(true)
    await wrapper.get('[data-testid="admin-app-submit"]').trigger('click')

    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.text()).toContain('只能绑定已启用且有效的控制策略')
  })
})
