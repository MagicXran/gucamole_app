export type BookingStatus = 'active' | 'cancelled' | string

export type BookingRecord = {
  id: number
  user_id: number
  app_name: string
  scheduled_for: string
  purpose: string
  note: string
  status: BookingStatus
  created_at: string | null
  cancelled_at: string | null
}

export type BookingCreatePayload = {
  app_name: string
  scheduled_for: string
  purpose: string
  note: string
}
