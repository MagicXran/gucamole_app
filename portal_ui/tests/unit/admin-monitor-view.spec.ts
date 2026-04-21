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

describe('AdminMonitorView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('restores monitor refresh interval, started time, duration, and status mapping', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: { user_id: 1, username: 'admin', display_name: '管理员', is_admin: true },
    })

    vi.mocked(opsApi.getAdminMonitorOverview).mockResolvedValue({
      data: {
        total_online: 3,
        total_sessions: 5,
        apps: [{ app_id: 9, app_name: 'Fluent', icon: 'desktop', active_count: 2 }],
      },
      headers: {},
    } as never)
    vi.mocked(opsApi.getAdminMonitorSessions)
      .mockResolvedValueOnce({
        data: {
          sessions: [
            {
              session_id: 'session-1',
              display_name: '测试员',
              username: 'tester',
              app_name: 'Fluent',
              status: 'active',
              started_at: '2026-04-18 10:00:00',
              last_heartbeat: '2026-04-18 10:00:05',
              duration_seconds: 30,
            },
          ],
        },
        headers: {},
      } as never)
      .mockResolvedValueOnce({
        data: {
          sessions: [
            {
              session_id: 'session-1',
              display_name: '测试员',
              username: 'tester',
              app_name: 'Fluent',
              status: 'reclaim_pending',
              started_at: '2026-04-18 10:00:00',
              last_heartbeat: '2026-04-18 10:00:05',
              duration_seconds: 30,
            },
          ],
        },
        headers: {},
      } as never)
    vi.mocked(opsApi.reclaimAdminSession).mockResolvedValue({
      data: { session_id: 'session-1', status: 'reclaim_pending' },
      headers: {},
    } as never)

    const { default: AdminMonitorView } = await import('@/modules/admin/views/AdminMonitorView.vue')
    const wrapper = mount(AdminMonitorView)
    await flushPromises()

    expect(wrapper.text()).toContain('在线 3 人')
    expect(wrapper.text()).toContain('Fluent')
    expect(wrapper.text()).toContain('2026-04-18 10:00:00')
    expect(wrapper.text()).toContain('30s')
    expect(wrapper.text()).toContain('在线')
    expect((wrapper.get('[data-testid="admin-monitor-interval"]').element as HTMLSelectElement).value).toBe('30')
    await wrapper.get('[data-testid="admin-session-reclaim-session-1"]').trigger('click')
    await flushPromises()

    expect(opsApi.reclaimAdminSession).toHaveBeenCalledWith('session-1')
    expect(wrapper.text()).toContain('回收中')
  })

  it('restarts auto refresh when monitor interval changes', async () => {
    vi.useFakeTimers()
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: { user_id: 1, username: 'admin', display_name: '管理员', is_admin: true },
    })

    vi.mocked(opsApi.getAdminMonitorOverview).mockResolvedValue({
      data: {
        total_online: 1,
        total_sessions: 1,
        apps: [],
      },
      headers: {},
    } as never)
    vi.mocked(opsApi.getAdminMonitorSessions).mockResolvedValue({
      data: { sessions: [] },
      headers: {},
    } as never)

    const { default: AdminMonitorView } = await import('@/modules/admin/views/AdminMonitorView.vue')
    const wrapper = mount(AdminMonitorView)
    await flushPromises()

    vi.mocked(opsApi.getAdminMonitorOverview).mockClear()
    vi.mocked(opsApi.getAdminMonitorSessions).mockClear()

    await wrapper.get('[data-testid="admin-monitor-interval"]').setValue('10')
    await vi.advanceTimersByTimeAsync(10_000)
    await flushPromises()

    expect(opsApi.getAdminMonitorOverview).toHaveBeenCalledTimes(1)
    expect(opsApi.getAdminMonitorSessions).toHaveBeenCalledTimes(1)
  })
})
