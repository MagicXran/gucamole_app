import { bootstrapPortalApp } from './bootstrap'
import router from './router'
import './styles/index.scss'

bootstrapPortalApp(router).then((result) => {
  if (!result) return
  result.app.mount('#app')
})
