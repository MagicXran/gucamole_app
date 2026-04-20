import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  cancelBooking as cancelBookingRequest,
  createBooking as createBookingRequest,
  listBookings,
} from '@/modules/my/services/api/bookings'
import type { BookingCreatePayload, BookingRecord } from '@/modules/my/types/bookings'

function resolveErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

function replaceBooking(bookings: BookingRecord[], nextBooking: BookingRecord) {
  return bookings.map((booking) => (booking.id === nextBooking.id ? nextBooking : booking))
}

export const useBookingsStore = defineStore('my-bookings', () => {
  const bookings = ref<BookingRecord[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const saving = ref(false)
  const cancellingId = ref<number | null>(null)
  const errorMessage = ref('')
  const formErrorMessage = ref('')

  async function loadBookings() {
    loading.value = true
    errorMessage.value = ''

    try {
      const response = await listBookings()
      bookings.value = response.data
    } catch (error) {
      bookings.value = []
      errorMessage.value = resolveErrorMessage(error, '加载预约失败')
    } finally {
      loaded.value = true
      loading.value = false
    }
  }

  async function createBooking(payload: BookingCreatePayload) {
    saving.value = true
    formErrorMessage.value = ''

    try {
      const response = await createBookingRequest(payload)
      bookings.value = [response.data, ...bookings.value]
      return response.data
    } catch (error) {
      formErrorMessage.value = resolveErrorMessage(error, '新增预约失败')
      return null
    } finally {
      saving.value = false
    }
  }

  async function cancelBooking(bookingId: number) {
    cancellingId.value = bookingId
    errorMessage.value = ''

    try {
      const response = await cancelBookingRequest(bookingId)
      bookings.value = replaceBooking(bookings.value, response.data)
      return response.data
    } catch (error) {
      errorMessage.value = resolveErrorMessage(error, '取消预约失败')
      return null
    } finally {
      cancellingId.value = null
    }
  }

  return {
    bookings,
    loading,
    loaded,
    saving,
    cancellingId,
    errorMessage,
    formErrorMessage,
    loadBookings,
    createBooking,
    cancelBooking,
  }
})
