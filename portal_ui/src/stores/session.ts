import { defineStore } from 'pinia'
import { ref } from 'vue'

import { PORTAL_TOKEN_KEY, PORTAL_USER_KEY } from '@/constants/auth'
import { getSessionBootstrap } from '@/services/api/session'
import type { SessionMenuNode, SessionUser } from '@/types/auth'

export const useSessionStore = defineStore('session', () => {
  const authenticated = ref(false)
  const authSource = ref('anonymous')
  const user = ref<SessionUser | null>(null)
  const capabilities = ref<string[]>([])
  const menuTree = ref<SessionMenuNode[]>([])
  const orgContext = ref<Record<string, unknown>>({})
  const bootstrapLoaded = ref(false)
  const bootstrapError = ref('')

  async function bootstrap() {
    bootstrapError.value = ''
    try {
      const response = await getSessionBootstrap()
      const payload = response.data

      authenticated.value = payload.authenticated
      authSource.value = payload.auth_source
      user.value = payload.user
      capabilities.value = payload.capabilities
      menuTree.value = payload.menu_tree
      orgContext.value = payload.org_context

      if (payload.user) {
        localStorage.setItem(PORTAL_USER_KEY, JSON.stringify(payload.user))
      } else {
        localStorage.removeItem(PORTAL_TOKEN_KEY)
        localStorage.removeItem(PORTAL_USER_KEY)
      }
    } catch (error) {
      authenticated.value = false
      authSource.value = 'anonymous'
      user.value = null
      capabilities.value = []
      menuTree.value = []
      orgContext.value = {}
      bootstrapError.value = error instanceof Error ? error.message : '会话初始化失败'
      localStorage.removeItem(PORTAL_TOKEN_KEY)
      localStorage.removeItem(PORTAL_USER_KEY)
    } finally {
      bootstrapLoaded.value = true
    }
  }

  return {
    authenticated,
    authSource,
    user,
    capabilities,
    menuTree,
    orgContext,
    bootstrapLoaded,
    bootstrapError,
    bootstrap,
  }
})
