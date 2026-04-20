import { createRouter, createWebHistory, type RouterHistory, type RouteRecordRaw } from 'vue-router'
import { getActivePinia } from 'pinia'

import { adminRoutes } from '@/modules/admin/routes'
import { computeRoutes } from '@/modules/compute/routes'
import { caseRoutes } from '@/modules/cases/routes'
import { myRoutes } from '@/modules/my/routes'
import { sdkRoutes } from '@/modules/sdk/routes'
import PortalShell from '@/shell/PortalShell.vue'
import { useNavigationStore } from '@/stores/navigation'
import { useSessionStore } from '@/stores/session'

export const appRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    component: PortalShell,
    children: [...computeRoutes, ...myRoutes, ...caseRoutes, ...sdkRoutes, ...adminRoutes],
  },
]

export function createPortalRouter(history: RouterHistory = createWebHistory(import.meta.env.BASE_URL)) {
  const router = createRouter({
    history,
    routes: appRoutes,
  })

  router.beforeEach((to) => {
    const activePinia = getActivePinia()

    if (to.matched.some((record) => record.meta.requiresAdmin)) {
      if (!activePinia) {
        return {
          path: '/',
          replace: true,
        }
      }

      const sessionStore = useSessionStore(activePinia)
      const navigationStore = useNavigationStore(activePinia)

      if (!sessionStore.user?.is_admin) {
        return {
          path: navigationStore.defaultPath || '/',
          replace: true,
        }
      }
    }

    if (to.path !== '/') {
      return true
    }

    if (!activePinia) {
      return true
    }

    const navigationStore = useNavigationStore(activePinia)
    if (!navigationStore.defaultPath || navigationStore.defaultPath === '/') {
      return true
    }

    return {
      path: navigationStore.defaultPath,
      replace: true,
    }
  })

  return router
}

const router = createPortalRouter()

export default router
