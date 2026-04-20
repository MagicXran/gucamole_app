import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { PORTAL_TOKEN_KEY, PORTAL_USER_KEY } from '@/constants/auth'
import { createPortalRouter } from '@/router'
import PortalSidebar from '@/shell/PortalSidebar.vue'
import PortalTopbar from '@/shell/PortalTopbar.vue'
import { useNavigationStore } from '@/stores/navigation'
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
    children: [
      { key: 'my-workspace', title: '个人空间', path: '/my/workspace' },
      { key: 'my-tasks', title: 'App任务', path: '/my/tasks' },
      { key: 'my-bookings', title: '预约登记', path: '/my/bookings' },
    ],
  },
]

describe('my center navigation shell', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: {
        user_id: 9,
        username: 'zhangsan',
        display_name: '张三',
        is_admin: false,
      },
      menuTree,
    })
  })

  it('keeps compute as the default landing group while resolving my breadcrumbs', () => {
    const navigationStore = useNavigationStore()

    expect(navigationStore.defaultPath).toBe('/compute/commercial')
    expect(navigationStore.resolveBreadcrumb('/my/workspace')).toEqual(['我的', '个人空间'])
    expect(navigationStore.resolveBreadcrumb('/my/tasks')).toEqual(['我的', 'App任务'])
    expect(navigationStore.resolveBreadcrumb('/my/bookings')).toEqual(['我的', '预约登记'])
  })

  it('renders the my menu group in the sidebar', () => {
    const wrapper = mount(PortalSidebar, {
      global: {
        stubs: {
          RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('我的')
    expect(wrapper.find('a[href="/my/workspace"]').text()).toContain('个人空间')
    expect(wrapper.find('a[href="/my/tasks"]').text()).toContain('App任务')
    expect(wrapper.find('a[href="/my/bookings"]').text()).toContain('预约登记')
  })

  it('registers minimal Vue routes for my center pages', async () => {
    const router = createPortalRouter(createMemoryHistory())
    await router.push('/my/workspace')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/my/workspace')

    await router.push('/my/tasks')
    expect(router.currentRoute.value.path).toBe('/my/tasks')

    await router.push('/my/bookings')
    expect(router.currentRoute.value.path).toBe('/my/bookings')
  })

  it('shows user identity, result center link, and clears session on logout', async () => {
    localStorage.setItem(PORTAL_TOKEN_KEY, 'token-a')
    localStorage.setItem(PORTAL_USER_KEY, '{"username":"zhangsan"}')

    const wrapper = mount(PortalTopbar)

    expect(wrapper.text()).toContain('张三')
    expect(wrapper.find('a[href="/portal/my/workspace"]').text()).toContain('结果中心')

    await wrapper.get('[data-testid="portal-logout"]').trigger('click.prevent')

    expect(localStorage.getItem(PORTAL_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(PORTAL_USER_KEY)).toBeNull()
  })
})
