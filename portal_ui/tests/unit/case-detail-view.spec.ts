import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { createPortalRouter } from '@/router'
import * as casesApi from '@/modules/cases/services/api/cases'
import * as commentsApi from '@/services/api/comments'
import { useNavigationStore } from '@/stores/navigation'
import { useSessionStore } from '@/stores/session'

const menuTree = [
  {
    key: 'compute',
    title: '计算资源',
    children: [{ key: 'compute-commercial', title: '商业软件', path: '/compute/commercial' }],
  },
  {
    key: 'cases',
    title: '任务案例',
    path: '/cases',
  },
]

function mockCaseDetail() {
  vi.spyOn(casesApi, 'getCaseDetail').mockResolvedValue({
    data: {
      id: 9,
      case_uid: 'case-nine',
      title: 'CFD 公开案例',
      summary: '公开包',
      app_id: 5,
      published_at: '2026-04-17 08:00:00',
      asset_count: 2,
      assets: [
        {
          id: 91,
          asset_kind: 'workspace_output',
          display_name: 'report.pdf',
          package_relative_path: 'assets/report.pdf',
          size_bytes: 1024,
          sort_order: 0,
        },
        {
          id: 92,
          asset_kind: 'workspace_output',
          display_name: 'mesh.cas',
          package_relative_path: 'assets/mesh.cas',
          size_bytes: 2048,
          sort_order: 1,
        },
      ],
    },
    headers: {},
  } as never)
}

describe('CaseDetailView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()

    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      menuTree,
    })
    vi.spyOn(commentsApi, 'listComments').mockResolvedValue({
      data: [],
      headers: {},
    } as never)
    vi.spyOn(commentsApi, 'createComment').mockResolvedValue({
      data: {
        id: 1,
        target_type: 'case',
        target_id: 9,
        user_id: 7,
        author_name: '测试用户',
        content: '新评论',
        created_at: '2026-04-18 10:00:00',
      },
      headers: {},
    } as never)
  })

  it('loads case detail, resolves breadcrumb, and triggers download/transfer actions', async () => {
    mockCaseDetail()
    vi.spyOn(casesApi, 'transferCase').mockResolvedValue({
      data: {
        case_id: 9,
        case_uid: 'case-nine',
        target_path: 'Cases/case-nine',
        asset_count: 2,
      },
      headers: {},
    } as never)
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    const router = createPortalRouter(createMemoryHistory())
    await router.push('/cases/9')
    await router.isReady()

    const navigationStore = useNavigationStore()
    const { default: CaseDetailView } = await import('@/modules/cases/views/CaseDetailView.vue')
    const wrapper = mount(CaseDetailView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect(casesApi.getCaseDetail).toHaveBeenCalledWith(9)
    expect(commentsApi.listComments).toHaveBeenCalledWith('case', 9)
    expect(navigationStore.resolveBreadcrumb('/cases/9')).toEqual(['任务案例', '案例详情'])
    expect(wrapper.text()).toContain('CFD 公开案例')
    expect(wrapper.text()).toContain('评论')
    expect(wrapper.text()).toContain('report.pdf')
    expect(wrapper.text()).toContain('mesh.cas')

    await wrapper.get('[data-testid="case-download"]').trigger('click')
    expect(openSpy).toHaveBeenCalledWith('/api/cases/9/download', '_blank', 'noopener')

    await wrapper.get('[data-testid="case-transfer"]').trigger('click')
    await flushPromises()

    expect(casesApi.transferCase).toHaveBeenCalledWith(9)
    expect(wrapper.text()).toContain('Cases/case-nine')
  })

  it('clears the previous transfer target when a new transfer starts and fails', async () => {
    mockCaseDetail()
    let rejectSecondTransfer: (error: Error) => void = () => {}
    vi.spyOn(casesApi, 'transferCase')
      .mockResolvedValueOnce({
        data: {
          case_id: 9,
          case_uid: 'case-nine',
          target_path: 'Cases/case-nine',
          asset_count: 2,
        },
        headers: {},
      } as never)
      .mockReturnValueOnce(
        new Promise((_resolve, reject) => {
          rejectSecondTransfer = reject
        }) as never,
      )

    const router = createPortalRouter(createMemoryHistory())
    await router.push('/cases/9')
    await router.isReady()

    const { default: CaseDetailView } = await import('@/modules/cases/views/CaseDetailView.vue')
    const wrapper = mount(CaseDetailView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    await wrapper.get('[data-testid="case-transfer"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Cases/case-nine')

    const secondTransfer = wrapper.get('[data-testid="case-transfer"]').trigger('click')
    await nextTick()
    expect(wrapper.text()).not.toContain('Cases/case-nine')

    rejectSecondTransfer(new Error('transfer failed'))
    await secondTransfer
    await flushPromises()

    expect(wrapper.text()).toContain('transfer failed')
    expect(wrapper.text()).not.toContain('Cases/case-nine')
  })
})
