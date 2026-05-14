<template>
  <section class="booking-view">
    <header class="booking-view__header">
      <div>
        <h1>预约登记</h1>
        <p>登记 App 使用意向；它不锁资源、不排队、不参与调度。</p>
      </div>
      <button type="button" data-testid="booking-open-create" @click="dialogOpen = true">
        新增预约
      </button>
    </header>

    <p v-if="bookingsStore.errorMessage" class="booking-view__error">{{ bookingsStore.errorMessage }}</p>

    <div v-if="bookingsStore.loading" class="booking-view__empty">预约加载中...</div>
    <div v-else-if="bookingsStore.bookings.length === 0" class="booking-view__empty">暂无预约登记</div>
    <div v-else class="booking-view__list">
      <article v-for="booking in bookingsStore.bookings" :key="booking.id" class="booking-card">
        <div>
          <h2>{{ booking.app_name }}</h2>
          <p>{{ booking.purpose }}</p>
        </div>
        <dl>
          <div>
            <dt>预约时间</dt>
            <dd>{{ booking.scheduled_for }}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>{{ booking.status }}</dd>
          </div>
          <div v-if="booking.cancelled_at">
            <dt>取消时间</dt>
            <dd>{{ booking.cancelled_at }}</dd>
          </div>
        </dl>
        <footer>
          <button type="button" :data-testid="`booking-view-${booking.id}`" @click="selectedBooking = booking">
            查看
          </button>
          <button
            v-if="booking.status === 'active'"
            type="button"
            :data-testid="`booking-cancel-${booking.id}`"
            :disabled="bookingsStore.cancellingId === booking.id"
            @click="handleCancel(booking.id)"
          >
            {{ bookingsStore.cancellingId === booking.id ? '取消中...' : '取消预约' }}
          </button>
        </footer>
      </article>
    </div>

    <aside v-if="selectedBooking" class="booking-view__detail" data-testid="booking-detail">
      <header>
        <h2>{{ selectedBooking.app_name }}</h2>
        <button type="button" @click="selectedBooking = null">关闭详情</button>
      </header>
      <p><strong>预约时间：</strong>{{ selectedBooking.scheduled_for }}</p>
      <p><strong>用途：</strong>{{ selectedBooking.purpose }}</p>
      <p><strong>备注：</strong>{{ selectedBooking.note || '无' }}</p>
      <p><strong>状态：</strong>{{ selectedBooking.status }}</p>
    </aside>

    <BookingFormDialog
      :open="dialogOpen"
      :saving="bookingsStore.saving"
      :error-message="bookingsStore.formErrorMessage"
      @close="dialogOpen = false"
      @submit="handleCreate"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import BookingFormDialog from '@/modules/my/components/BookingFormDialog.vue'
import { useBookingsStore } from '@/modules/my/stores/bookings'
import type { BookingCreatePayload, BookingRecord } from '@/modules/my/types/bookings'

const bookingsStore = useBookingsStore()
const dialogOpen = ref(false)
const selectedBooking = ref<BookingRecord | null>(null)

async function handleCreate(payload: BookingCreatePayload) {
  const booking = await bookingsStore.createBooking(payload)
  if (booking) {
    selectedBooking.value = booking
    dialogOpen.value = false
  }
}

async function handleCancel(bookingId: number) {
  const booking = await bookingsStore.cancelBooking(bookingId)
  if (booking && selectedBooking.value?.id === booking.id) {
    selectedBooking.value = booking
  }
}

onMounted(async () => {
  if (!bookingsStore.loaded) {
    await bookingsStore.loadBookings()
  }
})
</script>

<style scoped>
.booking-view {
  display: grid;
  gap: 18px;
  padding: 24px;
  background: var(--portal-color-surface);
  border: 1px solid var(--portal-color-border);
  border-radius: 24px;
  box-shadow: var(--portal-shadow-soft);
}

.booking-view__header,
.booking-card footer,
.booking-view__detail header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.booking-view__list {
  display: grid;
  gap: 14px;
}

.booking-card,
.booking-view__detail,
.booking-view__empty {
  border: 1px solid var(--portal-color-border);
  border-radius: 18px;
  padding: 16px;
  background: var(--portal-color-page);
}

.booking-card {
  display: grid;
  gap: 12px;
}

dl {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 0;
}

dt {
  color: var(--portal-color-muted);
  font-size: 12px;
}

dd {
  margin: 4px 0 0;
  color: var(--portal-color-ink);
}

button {
  min-height: 40px;
  border: 1px solid var(--portal-color-border);
  border-radius: 999px;
  background: var(--portal-color-surface);
  color: var(--portal-color-ink);
  padding: 0 14px;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

.booking-view__header button,
.booking-card button:last-child {
  background: var(--portal-color-primary);
  color: #fff;
  border-color: var(--portal-color-primary);
}

button:hover:not(:disabled) {
  border-color: var(--portal-color-primary);
  color: var(--portal-color-primary);
}

.booking-view__header button:hover,
.booking-card button:last-child:hover {
  background: var(--portal-color-primary-strong);
  color: #fff;
}

h1 {
  margin: 0 0 12px;
  font-size: 32px;
  color: var(--portal-color-ink);
  letter-spacing: -0.02em;
}

h2,
p {
  margin: 0;
}

p {
  color: var(--portal-color-body);
}

.booking-view__error {
  padding: 12px 14px;
  border-radius: 16px;
  background: #fff5f7;
  color: var(--portal-color-danger);
}
</style>
