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
})
