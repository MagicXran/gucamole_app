import { createRouter, createMemoryHistory } from 'vue-router'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import App from '@/App.vue'

describe('App shell', () => {
  it('renders the active route content inside the app shell', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div data-testid="route-content">empty shell</div>' }
        }
      ]
    })

    router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router]
      }
    })

    expect(wrapper.find('[data-testid="route-content"]').text()).toBe('empty shell')
  })
})
