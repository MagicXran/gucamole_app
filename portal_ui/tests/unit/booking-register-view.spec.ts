import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import BookingRegisterView from '@/modules/my/views/BookingRegisterView.vue'
import { myRoutes } from '@/modules/my/routes'

const apiMocks = vi.hoisted(() => ({
  listBookings: vi.fn(),
  createBooking: vi.fn(),
  cancelBooking: vi.fn(),
}))

vi.mock('@/modules/my/services/api/bookings', () => apiMocks)

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/my/bookings', component: BookingRegisterView }],
  })
}

describe('BookingRegisterView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    apiMocks.listBookings.mockResolvedValue({
      data: [
        {
          id: 1,
          user_id: 7,
          app_name: 'Fluent',
          scheduled_for: '2026-04-20 09:00:00',
          purpose: '算例复核',
          note: '上午先跑一轮',
          status: 'active',
          created_at: '2026-04-16 12:00:00',
          cancelled_at: null,
        },
        {
          id: 2,
          user_id: 7,
          app_name: 'COMSOL',
          scheduled_for: '2026-04-19 10:00:00',
          purpose: '已取消预约',
          note: '',
          status: 'cancelled',
          created_at: '2026-04-16 11:00:00',
          cancelled_at: '2026-04-16 13:00:00',
        },
      ],
      headers: {},
    } as never)
    apiMocks.createBooking.mockResolvedValue({
      data: {
        id: 3,
        user_id: 7,
        app_name: 'Abaqus',
        scheduled_for: '2026-04-21 13:30:00',
        purpose: '热处理仿真预约',
        note: '需要提前导入材料参数',
        status: 'active',
        created_at: '2026-04-16 14:00:00',
        cancelled_at: null,
      },
      headers: {},
    } as never)
    apiMocks.cancelBooking.mockResolvedValue({
      data: {
        id: 1,
        user_id: 7,
        app_name: 'Fluent',
        scheduled_for: '2026-04-20 09:00:00',
        purpose: '算例复核',
        note: '上午先跑一轮',
        status: 'cancelled',
        created_at: '2026-04-16 12:00:00',
        cancelled_at: '2026-04-16 15:00:00',
      },
      headers: {},
    } as never)
  })

  it('replaces the placeholder route with the real booking view', () => {
    const bookingRoute = myRoutes.find((route) => route.path === '/my/bookings')

    expect(bookingRoute?.component).toBe(BookingRegisterView)
  })

  it('loads bookings, shows detail, creates a booking, and cancels active booking', async () => {
    const router = buildRouter()
    await router.push('/my/bookings')
    await router.isReady()

    const wrapper = mount(BookingRegisterView, {
      global: {
        plugins: [createPinia(), router],
      },
    })
    await flushPromises()

    expect(apiMocks.listBookings).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('预约登记')
    expect(wrapper.text()).toContain('Fluent')
    expect(wrapper.text()).toContain('COMSOL')

    await wrapper.get('[data-testid="booking-view-1"]').trigger('click')
    expect(wrapper.text()).toContain('上午先跑一轮')
    expect(wrapper.text()).toContain('算例复核')

    await wrapper.get('[data-testid="booking-open-create"]').trigger('click')
    await wrapper.get('[data-testid="booking-app-name"]').setValue('Abaqus')
    await wrapper.get('[data-testid="booking-scheduled-for"]').setValue('2026-04-21T13:30')
    await wrapper.get('[data-testid="booking-purpose"]').setValue('热处理仿真预约')
    await wrapper.get('[data-testid="booking-note"]').setValue('需要提前导入材料参数')
    await wrapper.get('[data-testid="booking-form-submit"]').trigger('submit')
    await flushPromises()

    expect(apiMocks.createBooking).toHaveBeenCalledWith({
      app_name: 'Abaqus',
      scheduled_for: '2026-04-21T13:30',
      purpose: '热处理仿真预约',
      note: '需要提前导入材料参数',
    })
    expect(wrapper.text()).toContain('Abaqus')

    await wrapper.get('[data-testid="booking-cancel-1"]').trigger('click')
    await flushPromises()

    expect(apiMocks.cancelBooking).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('2026-04-16 15:00:00')
  })
})
