import { computed } from 'vue'
import { defineStore } from 'pinia'
import { storeToRefs } from 'pinia'

import { useSessionStore } from '@/stores/session'
import type { SessionMenuNode } from '@/types/auth'

export const useNavigationStore = defineStore('navigation', () => {
  const sessionStore = useSessionStore()
  const { menuTree: sessionMenuTree } = storeToRefs(sessionStore)
  const menuTree = computed<SessionMenuNode[]>(() => sessionMenuTree.value)
  const defaultPath = computed(() => menuTree.value[0]?.children?.[0]?.path || menuTree.value[0]?.path)

  function resolveBreadcrumb(path: string): string[] {
    if (path.startsWith('/compute/pools/')) {
      const computeGroup = menuTree.value.find((group) => group.key === 'compute')
      if (computeGroup) {
        return [computeGroup.title, '应用详情']
      }
    }

    if (path.startsWith('/cases/')) {
      const caseGroup = menuTree.value.find((group) => group.key === 'cases')
      if (caseGroup) {
        return [caseGroup.title, '案例详情']
      }
    }

    if (path === '/sdk/cloud') {
      return ['SDK中心', '云平台SDK']
    }

    if (path === '/sdk/simulation-app') {
      return ['SDK中心', '仿真AppSDK']
    }

    if (path === '/admin') {
      return ['系统管理']
    }

    for (const group of menuTree.value) {
      for (const child of group.children || []) {
        if (child.path === path) {
          return [group.title, child.title]
        }
      }
      if (group.path === path) {
        return [group.title]
      }
    }
    return []
  }

  return {
    defaultPath,
    menuTree,
    resolveBreadcrumb,
  }
})
