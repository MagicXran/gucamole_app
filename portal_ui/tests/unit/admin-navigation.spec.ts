import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import AdminDashboardView from '@/modules/admin/views/AdminDashboardView.vue'
import { createPortalRouter } from '@/router'
import PortalSidebar from '@/shell/PortalSidebar.vue'
import { useNavigationStore } from '@/stores/navigation'
import { useSessionStore } from '@/stores/session'

const adminMenuTree = [
  {
    key: 'compute',
    title: '计算资源',
    children: [{ key: 'compute-commercial', title: '商业软件', path: '/compute/commercial' }],
  },
  {
    key: 'admin',
    title: '系统管理',
    children: [
      { key: 'admin-analytics', title: '统计看板', path: '/admin/analytics' },
      { key: 'admin-apps', title: 'App管理', path: '/admin/apps' },
      { key: 'admin-queues', title: '任务调度', path: '/admin/queues' },
      { key: 'admin-monitor', title: '资源监控', path: '/admin/monitor' },
      { key: 'admin-workers', title: 'Worker状态', path: '/admin/workers' },
    ],
  },
]

const regularMenuTree = [
  {
    key: 'compute',
    title: '计算资源',
    children: [{ key: 'compute-commercial', title: '商业软件', path: '/compute/commercial' }],
  },
]

describe('admin navigation shell', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('shows admin menu and routes only for admins while keeping compute as default landing', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: {
        user_id: 1,
        username: 'admin',
        display_name: '管理员',
        is_admin: true,
      },
      menuTree: adminMenuTree,
    })

    const navigationStore = useNavigationStore()
    expect(navigationStore.defaultPath).toBe('/compute/commercial')
    expect(navigationStore.resolveBreadcrumb('/admin/analytics')).toEqual(['系统管理', '统计看板'])
    expect(navigationStore.resolveBreadcrumb('/admin/apps')).toEqual(['系统管理', 'App管理'])
    expect(navigationStore.resolveBreadcrumb('/admin/queues')).toEqual(['系统管理', '任务调度'])
    expect(navigationStore.resolveBreadcrumb('/admin/monitor')).toEqual(['系统管理', '资源监控'])
    expect(navigationStore.resolveBreadcrumb('/admin/workers')).toEqual(['系统管理', 'Worker状态'])

    const wrapper = mount(PortalSidebar, {
      global: {
        stubs: {
          RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('系统管理')
    expect(wrapper.find('a[href="/admin/analytics"]').text()).toContain('统计看板')
    expect(wrapper.find('a[href="/admin/apps"]').text()).toContain('App管理')

    const dashboard = mount(AdminDashboardView, {
      global: {
        stubs: {
          RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        },
      },
    })
    expect(dashboard.find('a[href="/admin/analytics"]').text()).toContain('统计看板')
    expect(dashboard.find('a[href="/admin/apps"]').text()).toContain('App管理')
    expect(dashboard.find('a[href="/admin/queues"]').text()).toContain('任务调度')

    const router = createPortalRouter(createMemoryHistory())
    await router.push('/admin/analytics')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/admin/analytics')
    expect(router.currentRoute.value.matched).toHaveLength(2)

    await router.push('/admin/apps')
    expect(router.currentRoute.value.path).toBe('/admin/apps')
    expect(router.currentRoute.value.matched).toHaveLength(2)

    await router.push('/admin/queues')
    expect(router.currentRoute.value.path).toBe('/admin/queues')
    expect(router.currentRoute.value.matched).toHaveLength(2)

    await router.push('/admin/monitor')
    expect(router.currentRoute.value.path).toBe('/admin/monitor')
    expect(router.currentRoute.value.matched).toHaveLength(2)

    await router.push('/admin/workers')
    expect(router.currentRoute.value.path).toBe('/admin/workers')
    expect(router.currentRoute.value.matched).toHaveLength(2)
  })

  it('keeps admin menu hidden for regular users', () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: {
        user_id: 9,
        username: 'zhangsan',
        display_name: '张三',
        is_admin: false,
      },
      menuTree: regularMenuTree,
    })

    const wrapper = mount(PortalSidebar, {
      global: {
        stubs: {
          RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).not.toContain('系统管理')
    expect(wrapper.find('a[href="/admin/analytics"]').exists()).toBe(false)
    expect(wrapper.find('a[href="/admin/apps"]').exists()).toBe(false)
  })

  it('redirects regular users away from direct admin routes', async () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: {
        user_id: 9,
        username: 'zhangsan',
        display_name: '张三',
        is_admin: false,
      },
      menuTree: regularMenuTree,
    })

    const router = createPortalRouter(createMemoryHistory())
    await router.push('/admin/analytics')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/compute/commercial')
    expect(router.currentRoute.value.matched.some((route) => route.meta.requiresAdmin)).toBe(false)
  })
})
