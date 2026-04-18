import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import PortalShell from '@/shell/PortalShell.vue'
import { createPortalRouter } from '@/router'
import * as computeApi from '@/services/api/compute'
import { useSessionStore } from '@/stores/session'

const computeMenuTree = [
  {
    key: 'compute',
    title: '计算资源',
    children: [
      { key: 'compute-commercial', title: '商业软件', path: '/compute/commercial' },
      { key: 'compute-simulation', title: '仿真APP', path: '/compute/simulation' },
      { key: 'compute-tools', title: '计算工具', path: '/compute/tools' },
    ],
  },
]

describe('PortalShell', () => {
  let router = createPortalRouter(createMemoryHistory())
  let pinia = createPinia()

  beforeEach(() => {
    router = createPortalRouter(createMemoryHistory())
    pinia = createPinia()
    setActivePinia(pinia)
    vi.restoreAllMocks()
    vi.spyOn(computeApi, 'listRemoteApps').mockResolvedValue({
      data: [],
      headers: {},
    } as never)
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: {
        user_id: 1,
        username: 'admin',
        display_name: '管理员',
        is_admin: true,
      },
      menuTree: computeMenuTree,
    })
  })

  it('renders compute navigation and commercial software landing content', async () => {
    router.push('/compute/commercial')
    await router.isReady()

    const wrapper = mount(PortalShell, {
      global: {
        plugins: [pinia, router],
      },
    })

    expect(wrapper.text()).toContain('管理员')
    expect(wrapper.text()).toContain('计算资源')
    expect(wrapper.text()).toContain('商业软件')
    expect(wrapper.text()).toContain('可用软件列表')
  })

  it('renders simulation app route content', async () => {
    router.push('/compute/simulation')
    await router.isReady()

    const wrapper = mount(PortalShell, {
      global: {
        plugins: [pinia, router],
      },
    })

    expect(wrapper.text()).toContain('仿真应用列表')
  })

  it('renders compute tools route content', async () => {
    router.push('/compute/tools')
    await router.isReady()

    const wrapper = mount(PortalShell, {
      global: {
        plugins: [pinia, router],
      },
    })

    expect(wrapper.text()).toContain('计算工具列表')
  })

  it('renders top-level navigation links when a menu node carries a path', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      menuTree: [{ key: 'compute-tools', title: '计算工具', path: '/compute/tools' }],
    })
    router.push('/compute/tools')
    await router.isReady()

    const wrapper = mount(PortalShell, {
      global: {
        plugins: [pinia, router],
      },
    })

    expect(wrapper.find('a[href="/compute/tools"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('计算工具')
  })
})
