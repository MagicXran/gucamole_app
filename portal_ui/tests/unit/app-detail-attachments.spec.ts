import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import * as computeApi from '@/services/api/compute'
import AppDetailView from '@/modules/compute/views/AppDetailView.vue'
import { createPortalRouter } from '@/router'
import { useComputeStore } from '@/stores/compute'

describe('AppDetailView attachments', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders grouped attachment content from backend', async () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 1,
        pool_id: 10,
        app_kind: 'commercial_software',
        name: 'ANSYS Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 1,
        script_profile_key: 'ansys',
        script_profile_name: 'ANSYS',
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
        max_concurrent: 2,
        has_capacity: true,
      },
    ] as never
    store.loaded = true
    vi.spyOn(computeApi, 'getPoolAttachments').mockResolvedValue({
      data: {
        pool_id: 10,
        tutorial_docs: [{ id: 1, title: '用户手册', summary: 'PDF', link_url: 'https://example/doc.pdf', sort_order: 1 }],
        video_resources: [{ id: 2, title: '演示视频', summary: 'MP4', link_url: 'https://example/video', sort_order: 2 }],
        plugin_downloads: [{ id: 3, title: '插件包', summary: 'ZIP', link_url: 'https://example/plugin.zip', sort_order: 3 }],
      },
      headers: {},
    } as never)

    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
        stubs: { RouterLink: { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('用户手册')
    expect(wrapper.text()).toContain('PDF')
    expect(wrapper.text()).toContain('演示视频')
    expect(wrapper.text()).toContain('MP4')
    expect(wrapper.text()).toContain('插件包')
    expect(wrapper.text()).toContain('ZIP')
    expect(wrapper.get('[href="https://example/doc.pdf"]').text()).toContain('用户手册')
  })

  it('reloads attachments when route pool changes in the same component instance', async () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 1,
        pool_id: 10,
        app_kind: 'commercial_software',
        name: 'ANSYS Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 1,
        script_profile_key: 'ansys',
        script_profile_name: 'ANSYS',
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
        max_concurrent: 2,
        has_capacity: true,
      },
      {
        id: 2,
        pool_id: 11,
        app_kind: 'commercial_software',
        name: 'COMSOL',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: false,
        script_runtime_id: null,
        script_profile_key: null,
        script_profile_name: null,
        script_schedulable: false,
        script_status_code: '',
        script_status_label: '',
        script_status_tone: '',
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
    vi.spyOn(computeApi, 'getPoolAttachments').mockImplementation((poolId: number) =>
      Promise.resolve({
        data: {
          pool_id: poolId,
          tutorial_docs: [{ id: poolId, title: `手册-${poolId}`, summary: '', link_url: `https://example/${poolId}`, sort_order: 1 }],
          video_resources: [],
          plugin_downloads: [],
        },
        headers: {},
      } as never),
    )

    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
        stubs: { RouterLink: { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('手册-10')

    await router.push('/compute/pools/11')
    await flushPromises()

    expect(wrapper.text()).toContain('手册-11')
    expect(wrapper.text()).not.toContain('手册-10')
  })

  it('does not render unsafe historical attachment links', async () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 1,
        pool_id: 10,
        app_kind: 'commercial_software',
        name: 'ANSYS Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: false,
        script_runtime_id: null,
        script_profile_key: null,
        script_profile_name: null,
        script_schedulable: false,
        script_status_code: '',
        script_status_label: '',
        script_status_tone: '',
        script_status_summary: '',
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
    vi.spyOn(computeApi, 'getPoolAttachments').mockResolvedValue({
      data: {
        pool_id: 10,
        tutorial_docs: [
          { id: 1, title: '安全手册', summary: 'PDF', link_url: 'https://example/doc.pdf', sort_order: 1 },
          { id: 2, title: '危险脚本', summary: 'XSS', link_url: 'javascript:alert(1)', sort_order: 2 },
        ],
        video_resources: [{ id: 3, title: '危险数据', summary: 'bad', link_url: 'data:text/html,boom', sort_order: 3 }],
        plugin_downloads: [{ id: 4, title: '安全插件', summary: 'ZIP', link_url: 'http://example/plugin.zip', sort_order: 4 }],
      },
      headers: {},
    } as never)

    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
        stubs: { RouterLink: { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('安全手册')
    expect(wrapper.text()).toContain('安全插件')
    expect(wrapper.text()).not.toContain('危险脚本')
    expect(wrapper.text()).not.toContain('危险数据')
    expect(wrapper.find('[href="javascript:alert(1)"]').exists()).toBe(false)
    expect(wrapper.find('[href="data:text/html,boom"]').exists()).toBe(false)
  })

  it('ignores stale attachment responses after switching pools quickly', async () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 1,
        pool_id: 10,
        app_kind: 'commercial_software',
        name: 'ANSYS Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 1,
        script_profile_key: 'ansys',
        script_profile_name: 'ANSYS',
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
        max_concurrent: 2,
        has_capacity: true,
      },
      {
        id: 2,
        pool_id: 11,
        app_kind: 'commercial_software',
        name: 'COMSOL',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: false,
        script_runtime_id: null,
        script_profile_key: null,
        script_profile_name: null,
        script_schedulable: false,
        script_status_code: '',
        script_status_label: '',
        script_status_tone: '',
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

    let resolvePool10: (value: unknown) => void = () => {}
    let resolvePool11: (value: unknown) => void = () => {}
    vi.spyOn(computeApi, 'getPoolAttachments').mockImplementation((poolId: number) => {
      if (poolId === 10) {
        return new Promise((resolve) => {
          resolvePool10 = resolve
        }) as never
      }
      return new Promise((resolve) => {
        resolvePool11 = resolve
      }) as never
    })

    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
        stubs: { RouterLink: { template: '<a><slot /></a>' } },
      },
    })

    await router.push('/compute/pools/11')
    resolvePool11({
      data: {
        pool_id: 11,
        tutorial_docs: [{ id: 11, title: '手册-11', summary: '', link_url: 'https://example/11', sort_order: 1 }],
        video_resources: [],
        plugin_downloads: [],
      },
      headers: {},
    })
    await flushPromises()

    resolvePool10({
      data: {
        pool_id: 10,
        tutorial_docs: [{ id: 10, title: '手册-10', summary: '', link_url: 'https://example/10', sort_order: 1 }],
        video_resources: [],
        plugin_downloads: [],
      },
      headers: {},
    })
    await flushPromises()

    expect(wrapper.text()).toContain('手册-11')
    expect(wrapper.text()).not.toContain('手册-10')
  })
})
