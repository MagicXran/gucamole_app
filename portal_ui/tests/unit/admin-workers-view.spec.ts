import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSessionStore } from '@/stores/session'

vi.mock('@/modules/admin/services/api/ops', () => ({
  cancelAdminQueue: vi.fn(),
  createAdminWorkerGroup: vi.fn(),
  createAdminWorkerNode: vi.fn(),
  getAdminMonitorOverview: vi.fn(),
  getAdminMonitorSessions: vi.fn(),
  issueAdminWorkerEnrollment: vi.fn(),
  listAdminQueues: vi.fn(),
  listAdminWorkerGroups: vi.fn(),
  listAdminWorkerNodes: vi.fn(),
  reclaimAdminSession: vi.fn(),
  revokeAdminWorkerNode: vi.fn(),
  rotateAdminWorkerToken: vi.fn(),
}))

const opsApi = await import('@/modules/admin/services/api/ops')

describe('AdminWorkersView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders worker groups and node readiness state', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: { user_id: 1, username: 'admin', display_name: '管理员', is_admin: true },
    })

    vi.mocked(opsApi.listAdminWorkerGroups).mockResolvedValue({
      data: {
        items: [
          {
            id: 3,
            group_key: 'solver',
            name: '求解节点组',
            description: '求解器',
            node_count: 2,
            active_node_count: 1,
            is_active: true,
          },
        ],
      },
      headers: {},
    } as never)
    vi.mocked(opsApi.listAdminWorkerNodes).mockResolvedValue({
      data: {
        items: [
          {
            id: 8,
            display_name: 'worker-8',
            expected_hostname: 'solver-08',
            group_name: '求解节点组',
            status: 'active',
            workspace_share: '\\\\server\\share',
            scratch_root: 'D:/scratch',
            software_ready_count: 1,
            software_total_count: 2,
          },
        ],
      },
      headers: {},
    } as never)

    const { default: AdminWorkersView } = await import('@/modules/admin/views/AdminWorkersView.vue')
    const wrapper = mount(AdminWorkersView)
    await flushPromises()

    expect(wrapper.text()).toContain('求解节点组')
    expect(wrapper.text()).toContain('worker-8')
    expect(wrapper.text()).toContain('1/2')
  })

  it('restores legacy worker diagnostics, enrollment state, and software inventory details', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: { user_id: 1, username: 'admin', display_name: '管理员', is_admin: true },
    })

    vi.mocked(opsApi.listAdminWorkerGroups).mockResolvedValue({
      data: {
        items: [
          {
            id: 3,
            group_key: 'solver',
            name: '求解节点组',
            description: '求解器',
            node_count: 2,
            active_node_count: 1,
            is_active: true,
          },
        ],
      },
      headers: {},
    } as never)
    vi.mocked(opsApi.listAdminWorkerNodes).mockResolvedValue({
      data: {
        items: [
          {
            id: 8,
            display_name: 'worker-8',
            expected_hostname: 'solver-08',
            group_name: '求解节点组',
            status: 'offline',
            workspace_share: '\\\\server\\share',
            scratch_root: 'D:/scratch',
            max_concurrent_tasks: 2,
            software_ready_count: 1,
            software_total_count: 2,
            latest_enrollment_status: 'issued',
            latest_enrollment_expires_at: '2026-04-22 10:00:00',
            last_heartbeat_at: '2026-04-21 09:30:00',
            last_error: 'license unavailable',
            software_inventory: {
              ansys_mapdl: { software_name: 'ANSYS MAPDL', ready: true, issues: [] },
              abaqus_cli: { software_name: 'Abaqus CLI', ready: false, issues: ['missing executable'] },
            },
          },
        ],
      },
      headers: {},
    } as never)

    const { default: AdminWorkersView } = await import('@/modules/admin/views/AdminWorkersView.vue')
    const wrapper = mount(AdminWorkersView)
    await flushPromises()

    expect(wrapper.text()).toContain('离线')
    expect(wrapper.text()).toContain('注册码：issued')
    expect(wrapper.text()).toContain('2026-04-22 10:00:00')
    expect(wrapper.text()).toContain('最近错误：license unavailable')
    expect(wrapper.text()).toContain('并发：2')

    await wrapper.get('[data-testid="admin-worker-inventory-8"]').trigger('click')
    expect(wrapper.text()).toContain('软件能力 · worker-8')
    expect(wrapper.text()).toContain('ANSYS MAPDL')
    expect(wrapper.text()).toContain('Abaqus CLI')
    expect(wrapper.text()).toContain('missing executable')
  })

  it('restores worker group/node creation and token lifecycle actions', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: { user_id: 1, username: 'admin', display_name: '管理员', is_admin: true },
    })

    vi.mocked(opsApi.listAdminWorkerGroups).mockResolvedValue({
      data: {
        items: [
          {
            id: 3,
            group_key: 'solver',
            name: '求解节点组',
            description: '求解器',
            node_count: 1,
            active_node_count: 1,
            is_active: true,
          },
        ],
      },
      headers: {},
    } as never)
    vi.mocked(opsApi.listAdminWorkerNodes).mockResolvedValue({
      data: {
        items: [
          {
            id: 8,
            display_name: 'worker-8',
            expected_hostname: 'solver-08',
            group_name: '求解节点组',
            status: 'active',
            workspace_share: '\\\\server\\share',
            scratch_root: 'D:/scratch',
            max_concurrent_tasks: 1,
            software_ready_count: 1,
            software_total_count: 1,
            latest_enrollment_status: '',
            software_inventory: {},
          },
        ],
      },
      headers: {},
    } as never)
    vi.mocked(opsApi.createAdminWorkerGroup).mockResolvedValue({ data: {}, headers: {} } as never)
    vi.mocked(opsApi.createAdminWorkerNode).mockResolvedValue({ data: {}, headers: {} } as never)
    vi.mocked(opsApi.issueAdminWorkerEnrollment).mockResolvedValue({
      data: { worker_node_id: 8, plain_token: 'enr_plain', expires_at: '2026-04-22 10:00:00' },
      headers: {},
    } as never)
    vi.mocked(opsApi.rotateAdminWorkerToken).mockResolvedValue({
      data: { worker_node_id: 8, plain_token: 'wkr_plain' },
      headers: {},
    } as never)
    vi.mocked(opsApi.revokeAdminWorkerNode).mockResolvedValue({
      data: { worker_node_id: 8, status: 'revoked' },
      headers: {},
    } as never)
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    const { default: AdminWorkersView } = await import('@/modules/admin/views/AdminWorkersView.vue')
    const wrapper = mount(AdminWorkersView)
    await flushPromises()

    await wrapper.get('[data-testid="admin-worker-create-group"]').trigger('click')
    await wrapper.get('[data-testid="worker-group-key"]').setValue('abaqus')
    await wrapper.get('[data-testid="worker-group-name"]').setValue('Abaqus 节点组')
    await wrapper.get('[data-testid="worker-group-desc"]').setValue('批处理节点')
    await wrapper.get('[data-testid="worker-group-batch"]').setValue(2)
    await wrapper.get('[data-testid="worker-group-submit"]').trigger('click')
    await flushPromises()
    expect(opsApi.createAdminWorkerGroup).toHaveBeenCalledWith({
      group_key: 'abaqus',
      name: 'Abaqus 节点组',
      description: '批处理节点',
      max_claim_batch: 2,
    })

    await wrapper.get('[data-testid="admin-worker-create-node"]').trigger('click')
    await wrapper.get('[data-testid="worker-node-group-id"]').setValue('3')
    await wrapper.get('[data-testid="worker-node-display-name"]').setValue('worker-9')
    await wrapper.get('[data-testid="worker-node-expected-hostname"]').setValue('solver-09')
    await wrapper.get('[data-testid="worker-node-scratch-root"]').setValue('D:/scratch')
    await wrapper.get('[data-testid="worker-node-workspace-share"]').setValue('\\\\server\\share')
    await wrapper.get('[data-testid="worker-node-max-concurrent"]').setValue(3)
    await wrapper.get('[data-testid="worker-node-submit"]').trigger('click')
    await flushPromises()
    expect(opsApi.createAdminWorkerNode).toHaveBeenCalledWith({
      group_id: 3,
      display_name: 'worker-9',
      expected_hostname: 'solver-09',
      scratch_root: 'D:/scratch',
      workspace_share: '\\\\server\\share',
      max_concurrent_tasks: 3,
    })

    await wrapper.get('[data-testid="admin-worker-enrollment-8"]').trigger('click')
    await flushPromises()
    expect(opsApi.issueAdminWorkerEnrollment).toHaveBeenCalledWith(8, { expires_hours: 24 })
    expect(wrapper.text()).toContain('enr_plain')

    await wrapper.get('[data-testid="admin-worker-rotate-token-8"]').trigger('click')
    await flushPromises()
    expect(opsApi.rotateAdminWorkerToken).toHaveBeenCalledWith(8)
    expect(wrapper.text()).toContain('wkr_plain')

    await wrapper.get('[data-testid="admin-worker-revoke-8"]').trigger('click')
    await flushPromises()
    expect(opsApi.revokeAdminWorkerNode).toHaveBeenCalledWith(8)
  })
})
