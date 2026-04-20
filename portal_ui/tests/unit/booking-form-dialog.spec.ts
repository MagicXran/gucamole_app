import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import BookingFormDialog from '@/modules/my/components/BookingFormDialog.vue'

describe('BookingFormDialog', () => {
  it('submits the minimum booking payload and emits close', async () => {
    const wrapper = mount(BookingFormDialog, {
      props: {
        open: true,
        saving: false,
        errorMessage: '',
      },
    })

    await wrapper.get('[data-testid="booking-app-name"]').setValue('Fluent')
    await wrapper.get('[data-testid="booking-scheduled-for"]').setValue('2026-04-21T13:30')
    await wrapper.get('[data-testid="booking-purpose"]').setValue('高炉热场仿真')
    await wrapper.get('[data-testid="booking-note"]').setValue('需要提前准备材料库')
    await wrapper.get('[data-testid="booking-form-submit"]').trigger('submit')

    expect(wrapper.emitted('submit')).toEqual([
      [
        {
          app_name: 'Fluent',
          scheduled_for: '2026-04-21T13:30',
          purpose: '高炉热场仿真',
          note: '需要提前准备材料库',
        },
      ],
    ])

    await wrapper.get('[data-testid="booking-form-close"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('does not render the form when closed', () => {
    const wrapper = mount(BookingFormDialog, {
      props: {
        open: false,
        saving: false,
        errorMessage: '',
      },
    })

    expect(wrapper.find('[data-testid="booking-form-submit"]').exists()).toBe(false)
  })
})
