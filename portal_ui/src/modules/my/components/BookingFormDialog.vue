<template>
  <div v-if="open" class="booking-dialog" role="dialog" aria-modal="true">
    <div class="booking-dialog__panel">
      <header class="booking-dialog__header">
        <div>
          <h2>新增预约</h2>
          <p>登记使用意向，不占资源、不进调度队列。</p>
        </div>
        <button type="button" data-testid="booking-form-close" @click="$emit('close')">关闭</button>
      </header>

      <form class="booking-dialog__form" data-testid="booking-form-submit" @submit.prevent="handleSubmit">
        <label>
          应用名称
          <input
            v-model.trim="form.app_name"
            data-testid="booking-app-name"
            required
            maxlength="200"
            placeholder="例如 Fluent"
          />
        </label>

        <label>
          预约时间
          <input
            v-model="form.scheduled_for"
            data-testid="booking-scheduled-for"
            required
            type="datetime-local"
          />
        </label>

        <label>
          用途
          <input
            v-model.trim="form.purpose"
            data-testid="booking-purpose"
            required
            maxlength="255"
            placeholder="这次要解决什么问题"
          />
        </label>

        <label>
          备注
          <textarea
            v-model.trim="form.note"
            data-testid="booking-note"
            maxlength="1000"
            rows="4"
            placeholder="可选：数据、时间窗口、特殊说明"
          />
        </label>

        <p v-if="errorMessage" class="booking-dialog__error">{{ errorMessage }}</p>

        <footer class="booking-dialog__actions">
          <button type="button" @click="$emit('close')">取消</button>
          <button type="submit" :disabled="saving">{{ saving ? '提交中...' : '提交预约' }}</button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'

import type { BookingCreatePayload } from '@/modules/my/types/bookings'

const props = defineProps<{
  open: boolean
  saving: boolean
  errorMessage: string
}>()

const emit = defineEmits<{
  close: []
  submit: [payload: BookingCreatePayload]
}>()

const form = reactive<BookingCreatePayload>({
  app_name: '',
  scheduled_for: '',
  purpose: '',
  note: '',
})

function resetForm() {
  form.app_name = ''
  form.scheduled_for = ''
  form.purpose = ''
  form.note = ''
}

function handleSubmit() {
  emit('submit', {
    app_name: form.app_name,
    scheduled_for: form.scheduled_for,
    purpose: form.purpose,
    note: form.note,
  })
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      resetForm()
    }
  },
)
</script>

<style scoped>
.booking-dialog {
  position: fixed;
  inset: 0;
  z-index: 30;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(10, 11, 13, 0.48);
  backdrop-filter: blur(6px);
}

.booking-dialog__panel {
  width: min(560px, 100%);
  display: grid;
  gap: 16px;
  padding: 24px;
  border: 1px solid var(--portal-color-border);
  border-radius: 24px;
  background: var(--portal-color-surface);
  box-shadow: 0 28px 90px rgba(10, 11, 13, 0.22);
}

.booking-dialog__header,
.booking-dialog__actions {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.booking-dialog__form {
  display: grid;
  gap: 14px;
}

label {
  display: grid;
  gap: 8px;
  color: var(--portal-color-ink);
  font-weight: 600;
  font-size: 14px;
}

input,
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid transparent;
  border-radius: 16px;
  padding: 12px 14px;
  background: var(--portal-color-surface-soft);
  color: var(--portal-color-ink);
  font: inherit;
  transition: border-color 0.2s ease, background 0.2s ease;
}

input:focus,
textarea:focus {
  outline: none;
  border-color: rgba(0, 82, 255, 0.2);
  background: var(--portal-color-surface);
}

button {
  min-height: 42px;
  border: 1px solid var(--portal-color-border);
  border-radius: 999px;
  background: var(--portal-color-surface);
  color: var(--portal-color-ink);
  padding: 0 16px;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

button[type='submit'] {
  background: var(--portal-color-primary);
  color: #fff;
  border-color: var(--portal-color-primary);
}

button:hover:not(:disabled) {
  border-color: var(--portal-color-primary);
  color: var(--portal-color-primary);
}

button[type='submit']:hover:not(:disabled) {
  background: var(--portal-color-primary-strong);
  color: #fff;
}

button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

h2,
p {
  margin: 0;
}

p {
  color: var(--portal-color-body);
}

.booking-dialog__error {
  padding: 12px 14px;
  border-radius: 16px;
  background: #fff5f7;
  color: var(--portal-color-danger);
}
</style>
