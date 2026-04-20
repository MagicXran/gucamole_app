import http from '@/services/http'
import type { BookingCreatePayload, BookingRecord } from '@/modules/my/types/bookings'

export function listBookings() {
  return http.get<BookingRecord[]>('/api/bookings')
}

export function createBooking(payload: BookingCreatePayload) {
  return http.post<BookingRecord>('/api/bookings', payload)
}

export function cancelBooking(bookingId: number) {
  return http.post<BookingRecord>(`/api/bookings/${bookingId}/cancel`)
}
