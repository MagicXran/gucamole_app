<template>
  <article
    class="app-card"
    role="button"
    tabindex="0"
    :aria-busy="launching ? 'true' : 'false'"
    @click="handleLaunch"
    @keydown.enter.prevent="handleLaunch"
  >
    <div class="app-card__header">
      <div>
        <h2>{{ app.name }}</h2>
        <p>{{ app.protocol.toUpperCase() }} · {{ launchLabel }}</p>
      </div>
      <span :class="['app-card__status', statusToneClass]">
        {{ app.resource_status_label || (app.has_capacity ? '可用' : '忙碌') }}
      </span>
    </div>

    <div class="app-card__meta">
      <span>运行 {{ app.active_count }}/{{ app.max_concurrent }}</span>
      <span>排队 {{ app.queued_count }}</span>
      <span v-if="app.supports_script">{{ app.script_status_label || '脚本模式' }}</span>
    </div>

    <div class="app-card__actions">
      <span v-if="launching" class="app-card__launching">启动中...</span>
      <RouterLink
        v-if="detailPoolId"
        class="app-card__link"
        :to="`/compute/pools/${detailPoolId}`"
        @click.stop
      >
        查看详情
      </RouterLink>
    </div>
    <p v-if="errorMessage" class="app-card__error">{{ errorMessage }}</p>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { launchRemoteApp } from '@/modules/compute/services/launch'
import type { ComputeAppCard } from '@/types/compute'

const props = defineProps<{
  app: ComputeAppCard
}>()

const statusToneClass = computed(() => `app-card__status--${props.app.resource_status_tone || 'neutral'}`)
const detailPoolId = computed(() => props.app.capacity_pool_id ?? props.app.pool_id ?? null)
const launchLabel = computed(() => {
  if (props.app.launch_target_kind === 'standalone_runtime') return '独立运行'
  return detailPoolId.value ? `容量池 #${detailPoolId.value}` : '容量池'
})
const launching = ref(false)
const errorMessage = ref('')

async function handleLaunch() {
  if (launching.value) {
    return
  }
  launching.value = true
  errorMessage.value = ''
  try {
    await launchRemoteApp(props.app.id, props.app.name, detailPoolId.value || 0)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '远程应用启动失败'
  } finally {
    launching.value = false
  }
}
</script>

<style scoped>
.app-card {
  display: grid;
  gap: 18px;
  padding: 20px;
  border: 1px solid var(--portal-color-border);
  border-radius: 24px;
  background: var(--portal-color-surface);
  box-shadow: var(--portal-shadow-soft);
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.app-card:hover {
  transform: translateY(-2px);
  border-color: rgba(0, 82, 255, 0.18);
  box-shadow: 0 16px 36px rgba(10, 11, 13, 0.08);
}

.app-card__header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

h2 {
  margin: 0 0 8px;
  font-size: 20px;
  color: var(--portal-color-ink);
}

p {
  margin: 0;
  color: var(--portal-color-body);
}

.app-card__status {
  align-self: start;
  min-height: 30px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.app-card__status--success {
  background: rgba(5, 177, 105, 0.1);
  color: var(--portal-color-success);
}

.app-card__status--warning {
  background: var(--portal-color-warning-surface);
  color: var(--portal-color-warning);
}

.app-card__status--danger {
  background: var(--portal-color-danger-surface);
  color: var(--portal-color-danger);
}

.app-card__status--info,
.app-card__status--neutral {
  background: var(--portal-color-surface-soft);
  color: #38537a;
}

.app-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--portal-color-body);
  font-size: 14px;
}

.app-card__meta span {
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--portal-color-surface-soft);
}

.app-card__link {
  color: var(--portal-color-primary);
  text-decoration: none;
  font-weight: 600;
}

.app-card__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.app-card__launching {
  color: var(--portal-color-body);
  font-size: 14px;
}

.app-card__error {
  margin: 0;
  color: var(--portal-color-danger);
  font-size: 14px;
}
</style>
