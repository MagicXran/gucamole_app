import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import AppDetailView from '@/modules/compute/views/AppDetailView.vue'
import * as casesApi from '@/modules/cases/services/api/cases'
import * as commentsApi from '@/services/api/comments'
import { createPortalRouter } from '@/router'
import * as computeApi from '@/services/api/compute'
import { useComputeStore } from '@/stores/compute'

describe('AppDetailView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(computeApi, 'getPoolAttachments').mockResolvedValue({
      data: {
        pool_id: 10,
        tutorial_docs: [],
        video_resources: [],
        plugin_downloads: [],
      },
      headers: {},
    } as never)
    vi.spyOn(casesApi, 'getCaseList').mockResolvedValue({
      data: [],
      headers: {},
    } as never)
    vi.spyOn(commentsApi, 'listComments').mockResolvedValue({
      data: [],
      headers: {},
    } as never)
    vi.spyOn(commentsApi, 'createComment').mockResolvedValue({
      data: {
        id: 1,
        target_type: 'app',
        target_id: 1,
        user_id: 7,
        author_name: '测试用户',
        content: '新评论',
        created_at: '2026-04-18 10:00:00',
      },
      headers: {},
    } as never)
  })

  it('renders app detail and attachment tab placeholders', async () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 1,
        pool_id: 10,
        name: 'ANSYS Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 1,
        script_profile_key: 'ansys_mapdl',
        script_profile_name: 'ANSYS MAPDL',
        script_schedulable: true,
        script_status_code: 'ready',
        script_status_label: '可调度',
        script_status_tone: 'success',
        script_status_summary: 'Worker 就绪',
        script_status_reason: '',
        resource_status_code: 'available',
        resource_status_label: '可用',
        resource_status_tone: 'success',
        active_count: 0,
        queued_count: 0,
        max_concurrent: 2,
        has_capacity: true,
      },
    ]
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('ANSYS Fluent')
    expect(wrapper.text()).toContain('教程文档')
    expect(wrapper.text()).toContain('视频资源')
    expect(wrapper.text()).toContain('插件下载')
    expect(wrapper.text()).toContain('评论')
  })

  it('loads app list when opening a detail route directly', async () => {
    vi.spyOn(computeApi, 'listRemoteApps').mockResolvedValue({
      data: [
        {
          id: 1,
          pool_id: 10,
          name: 'ANSYS Fluent',
          icon: 'desktop',
          protocol: 'rdp',
          supports_gui: true,
          supports_script: true,
          script_runtime_id: 1,
          script_profile_key: 'ansys_mapdl',
          script_profile_name: 'ANSYS MAPDL',
          script_schedulable: true,
          script_status_code: 'ready',
          script_status_label: '可调度',
          script_status_tone: 'success',
          script_status_summary: 'Worker 就绪',
          script_status_reason: '',
          resource_status_code: 'available',
          resource_status_label: '可用',
          resource_status_tone: 'success',
          active_count: 0,
          queued_count: 0,
          max_concurrent: 2,
          has_capacity: true,
        },
      ],
      headers: {},
    } as never)
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('ANSYS Fluent')
  })

  it('shows loading state before direct detail data resolves', async () => {
    vi.spyOn(computeApi, 'listRemoteApps').mockReturnValue(new Promise(() => {}) as never)
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('加载中')
    expect(wrapper.text()).not.toContain('应用不存在')
  })

  it('shows request error instead of pretending the app is missing', async () => {
    vi.spyOn(computeApi, 'listRemoteApps').mockRejectedValue(new Error('boom'))
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('boom')
    expect(wrapper.text()).not.toContain('应用不存在')
  })

  it('shows missing state after a successful empty direct load', async () => {
    vi.spyOn(computeApi, 'listRemoteApps').mockResolvedValue({
      data: [],
      headers: {},
    } as never)
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('应用不存在')
    expect(wrapper.text()).not.toContain('加载中')
  })

  it('returns to the source category for simulation and tool apps', async () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 3,
        pool_id: 30,
        app_kind: 'simulation_app',
        name: '仿真脚本平台',
        icon: 'terminal',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 3,
        script_profile_key: 'solver',
        script_profile_name: 'Solver',
        script_schedulable: true,
        script_status_code: 'ready',
        script_status_label: '可调度',
        script_status_tone: 'success',
        script_status_summary: '',
        script_status_reason: '',
        resource_status_code: 'available',
        resource_status_label: '可用',
        resource_status_tone: 'success',
        active_count: 0,
        queued_count: 0,
        max_concurrent: 1,
        has_capacity: true,
      },
    ] as never
    store.loaded = true
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/30')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.find('.app-detail__back').attributes('href')).toBe('/compute/simulation')
  })

  it('shows related public cases for the current app', async () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 9,
        pool_id: 10,
        app_kind: 'commercial_software',
        name: 'ANSYS Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 1,
        script_profile_key: 'ansys_mapdl',
        script_profile_name: 'ANSYS MAPDL',
        script_schedulable: true,
        script_status_code: 'ready',
        script_status_label: '可调度',
        script_status_tone: 'success',
        script_status_summary: 'Worker 就绪',
        script_status_reason: '',
        resource_status_code: 'available',
        resource_status_label: '可用',
        resource_status_tone: 'success',
        active_count: 0,
        queued_count: 0,
        max_concurrent: 2,
        has_capacity: true,
      },
    ] as never
    store.loaded = true
    vi.spyOn(casesApi, 'getCaseList').mockResolvedValue({
      data: [
        {
          id: 101,
          case_uid: 'case-101',
          title: 'Fluent 翼型算例',
          summary: '公开案例',
          app_id: 9,
          published_at: '2026-04-17T10:00:00Z',
          asset_count: 3,
        },
        {
          id: 102,
          case_uid: 'case-102',
          title: 'Fluent 管道算例',
          summary: '公开案例',
          app_id: 9,
          published_at: '2026-04-16T10:00:00Z',
          asset_count: 2,
        },
        {
          id: 103,
          case_uid: 'case-103',
          title: '其他软件案例',
          summary: '不应出现',
          app_id: 77,
          published_at: '2026-04-15T10:00:00Z',
          asset_count: 1,
        },
      ],
      headers: {},
    } as never)
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect(casesApi.getCaseList).toHaveBeenCalledTimes(1)
    expect(commentsApi.listComments).toHaveBeenCalledWith('app', 9)
    expect(wrapper.text()).toContain('相关案例')
    expect(wrapper.text()).toContain('Fluent 翼型算例')
    expect(wrapper.text()).toContain('Fluent 管道算例')
    expect(wrapper.text()).not.toContain('其他软件案例')
    expect(wrapper.find('[data-testid="related-case-link-101"]').attributes('href')).toBe('/cases/101')
  })

  it('shows empty related-case state without breaking attachments', async () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 9,
        pool_id: 10,
        app_kind: 'commercial_software',
        name: 'ANSYS Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 1,
        script_profile_key: 'ansys_mapdl',
        script_profile_name: 'ANSYS MAPDL',
        script_schedulable: true,
        script_status_code: 'ready',
        script_status_label: '可调度',
        script_status_tone: 'success',
        script_status_summary: 'Worker 就绪',
        script_status_reason: '',
        resource_status_code: 'available',
        resource_status_label: '可用',
        resource_status_tone: 'success',
        active_count: 0,
        queued_count: 0,
        max_concurrent: 2,
        has_capacity: true,
      },
    ] as never
    store.loaded = true
    vi.spyOn(casesApi, 'getCaseList').mockResolvedValue({
      data: [
        {
          id: 201,
          case_uid: 'case-201',
          title: '别的软件案例',
          summary: '不相关',
          app_id: 88,
          published_at: '2026-04-17T10:00:00Z',
          asset_count: 1,
        },
      ],
      headers: {},
    } as never)
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('暂无相关案例')
    expect(wrapper.text()).toContain('教程文档')
  })
})
