import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { createPortalRouter } from '@/router'
import * as casesApi from '@/modules/cases/services/api/cases'
import { useSessionStore } from '@/stores/session'

const menuTree = [
  {
    key: 'compute',
    title: '计算资源',
    children: [{ key: 'compute-commercial', title: '商业软件', path: '/compute/commercial' }],
  },
  {
    key: 'my',
    title: '我的',
    children: [{ key: 'my-workspace', title: '个人空间', path: '/my/workspace' }],
  },
  {
    key: 'cases',
    title: '任务案例',
    path: '/cases',
  },
]

describe('CaseListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()

    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      menuTree,
    })
  })

  it('loads cases, filters by keyword, and navigates to detail', async () => {
    vi.spyOn(casesApi, 'getCaseList').mockResolvedValue({
      data: [
        {
          id: 1,
          case_uid: 'case-alpha',
          title: '发动机热仿真案例',
          summary: '热分析',
          app_id: 8,
          published_at: '2026-04-17 12:00:00',
          asset_count: 2,
        },
        {
          id: 2,
          case_uid: 'case-beta',
          title: '结构求解案例',
          summary: '静力学',
          app_id: 9,
          published_at: '2026-04-16 09:00:00',
          asset_count: 1,
        },
      ],
      headers: {},
    } as never)

    const router = createPortalRouter(createMemoryHistory())
    await router.push('/cases')
    await router.isReady()

    const { default: CaseListView } = await import('@/modules/cases/views/CaseListView.vue')
    const wrapper = mount(CaseListView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect(casesApi.getCaseList).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('发动机热仿真案例')
    expect(wrapper.text()).toContain('结构求解案例')

    await wrapper.get('input[type="search"]').setValue('热仿真')

    expect(wrapper.text()).toContain('发动机热仿真案例')
    expect(wrapper.text()).not.toContain('结构求解案例')

    await wrapper.get('[data-testid="case-detail-link-1"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/cases/1')
  })
})
