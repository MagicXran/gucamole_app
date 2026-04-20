import { createApp } from 'vue'
import { createPinia, type Pinia } from 'pinia'
import type { Router } from 'vue-router'

import App from './App.vue'
import router from './router'
import { useSessionStore } from './stores/session'

type RedirectToLogin = () => void

function defaultRedirectToLogin() {
  window.location.href = '/login.html'
}

export function createPortalApp(activeRouter: Router = router, activePinia: Pinia = createPinia()) {
  const app = createApp(App)
  app.use(activePinia)
  app.use(activeRouter)
  return app
}

export async function bootstrapPortalApp(
  activeRouter: Router = router,
  redirectToLogin: RedirectToLogin = defaultRedirectToLogin,
) {
  const pinia = createPinia()
  const sessionStore = useSessionStore(pinia)

  await sessionStore.bootstrap()
  if (!sessionStore.authenticated) {
    redirectToLogin()
    return null
  }

  const app = createPortalApp(activeRouter, pinia)

  return {
    app,
    pinia,
    sessionStore,
  }
}
