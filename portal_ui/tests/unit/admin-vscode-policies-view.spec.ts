import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/modules/admin/services/api/vscodePolicies', () => ({
  createVscodeControlProfile: vi.fn(),
  deleteVscodeControlProfile: vi.fn(),
  getVscodeControlCatalog: vi.fn(),
  getVscodeControlProfileEffective: vi.fn(),
  listVscodeControlProfiles: vi.fn(),
  updateVscodeControlProfile: vi.fn(),
}))

const api = await import('@/modules/admin/services/api/vscodePolicies')

const catalog = {
  policy_version: 1,
  controls: [
    {
      code: 'terminal',
      category: 'execution',
      label: '集成终端',
      enforcement: 'AppLocker',
      risk: '只能启动允许的 shell。',
      requires_allowlists: ['allowed_shells'],
    },
    {
      code: 'copy_remote_to_local',
      category: 'data_channel',
      label: '远程复制到本地',
      enforcement: 'Guacamole',
      risk: '允许远程剪贴板内容复制到浏览器本地。',
      requires_allowlists: [],
    },
  ],
  default_permissions: {
    terminal: true,
    copy_remote_to_local: true,
  },
  locked_baseline: [
    { code: 'remoteapp_only', label: 'RemoteApp-only，禁止回退完整桌面' },
  ],
}

describe('AdminVscodePoliciesView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.mocked(api.getVscodeControlCatalog).mockResolvedValue({ data: catalog, headers: {} } as never)
    vi.mocked(api.listVscodeControlProfiles).mockResolvedValue({ data: { items: [] }, headers: {} } as never)
  })

  it('defaults every catalog permission to selected and supports clear/reset', async () => {
    const { default: AdminVscodePoliciesView } = await import('@/modules/admin/views/AdminVscodePoliciesView.vue')
    const wrapper = mount(AdminVscodePoliciesView)
    await flushPromises()

    await wrapper.get('[data-testid="vscode-policy-create"]').trigger('click')
    await flushPromises()

    expect((wrapper.get('[data-testid="vscode-control-terminal"]').element as HTMLInputElement).checked).toBe(true)
    expect((wrapper.get('[data-testid="vscode-control-copy_remote_to_local"]').element as HTMLInputElement).checked).toBe(true)
    expect(wrapper.get('[data-testid="vscode-policy-invalid-warning"]').text()).toContain('allowed_shells')

    await wrapper.get('[data-testid="vscode-policy-clear-all"]').trigger('click')
    expect((wrapper.get('[data-testid="vscode-control-terminal"]').element as HTMLInputElement).checked).toBe(false)
    expect((wrapper.get('[data-testid="vscode-control-copy_remote_to_local"]').element as HTMLInputElement).checked).toBe(false)

    await wrapper.get('[data-testid="vscode-policy-reset-defaults"]').trigger('click')
    expect((wrapper.get('[data-testid="vscode-control-terminal"]').element as HTMLInputElement).checked).toBe(true)
    expect((wrapper.get('[data-testid="vscode-control-copy_remote_to_local"]').element as HTMLInputElement).checked).toBe(true)
  })

  it('saves an enabled profile only after required allowlists are present', async () => {
    vi.mocked(api.createVscodeControlProfile).mockResolvedValue({
      data: {
        id: 1,
        profile_key: 'controlled-dev',
        display_name: '受控开发',
        description: '',
        policy_version: 1,
        revision: 1,
        is_active: true,
        valid: true,
        validation_errors: [],
        permissions: catalog.default_permissions,
        allowed_shells: ['C:\\Windows\\System32\\cmd.exe'],
        allowed_tools: [],
        allowed_debuggers: [],
        allowed_extensions: [],
        allowed_network_targets: [],
        user_data_root: 'C:\\PortalProfiles',
        extensions_root: 'C:\\PortalExtensions',
        default_workspace_template: '\\\\tsclient\\用户数据目录',
      },
      headers: {},
    } as never)

    const { default: AdminVscodePoliciesView } = await import('@/modules/admin/views/AdminVscodePoliciesView.vue')
    const wrapper = mount(AdminVscodePoliciesView)
    await flushPromises()

    await wrapper.get('[data-testid="vscode-policy-create"]').trigger('click')
    await wrapper.get('[data-testid="vscode-policy-key"]').setValue('controlled-dev')
    await wrapper.get('[data-testid="vscode-policy-name"]').setValue('受控开发')
    await wrapper.get('[data-testid="vscode-policy-shells"]').setValue('C:\\Windows\\System32\\cmd.exe')
    await wrapper.get('[data-testid="vscode-policy-active"]').setValue(true)
    await wrapper.get('[data-testid="vscode-policy-submit"]').trigger('click')
    await flushPromises()

    expect(api.createVscodeControlProfile).toHaveBeenCalledWith(expect.objectContaining({
      profile_key: 'controlled-dev',
      is_active: true,
      permissions: catalog.default_permissions,
      allowed_shells: ['C:\\Windows\\System32\\cmd.exe'],
    }))
  })
})
