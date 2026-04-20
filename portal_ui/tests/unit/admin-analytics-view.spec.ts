import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/modules/admin/services/api/analytics', () => ({
  getAdminAnalyticsOverview: vi.fn(),
}))

const analyticsApi = await import('@/modules/admin/services/api/analytics')

describe('AdminAnalyticsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders overview cards and ranking tables from analytics overview api', async () => {
    vi.mocked(analyticsApi.getAdminAnalyticsOverview).mockResolvedValue({
      data: {
        overview: {
          software_launches: 17,
          case_events: 18,
          active_users: 12,
          department_count: 11,
        },
        software_ranking: [
          { app_id: 11, app_name: 'Abaqus', launch_count: 5 },
          { app_id: 12, app_name: 'Fluent', launch_count: 2 },
        ],
        case_ranking: [
          {
            case_id: 31,
            case_uid: 'case-heat-001',
            case_title: '热轧工艺窗口案例',
            detail_count: 3,
            download_count: 2,
            transfer_count: 1,
            event_count: 6,
          },
        ],
        user_ranking: [
          {
            user_id: 7,
            username: 'alice',
            display_name: 'Alice',
            department: '研发一部',
            software_launch_count: 4,
            case_event_count: 2,
            event_count: 6,
          },
          {
            user_id: 9,
            username: 'bob',
            display_name: 'Bob',
            department: '未设置',
            software_launch_count: 1,
            case_event_count: 2,
            event_count: 3,
          },
        ],
        department_ranking: [
          { department: '研发一部', user_count: 1, event_count: 6 },
          { department: '未设置', user_count: 1, event_count: 3 },
        ],
      },
      headers: {},
    } as never)

    const { default: AdminAnalyticsView } = await import('@/modules/admin/views/AdminAnalyticsView.vue')
    const wrapper = mount(AdminAnalyticsView)
    await flushPromises()

    expect(wrapper.text()).toContain('统计看板')
    expect(wrapper.text()).toContain('软件启动次数')
    expect(wrapper.text()).toContain('17')
    expect(wrapper.text()).toContain('案例事件次数')
    expect(wrapper.text()).toContain('18')
    expect(wrapper.text()).toContain('Abaqus')
    expect(wrapper.text()).toContain('热轧工艺窗口案例')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('研发一部')
    expect(wrapper.text()).toContain('未设置')
  })
})
