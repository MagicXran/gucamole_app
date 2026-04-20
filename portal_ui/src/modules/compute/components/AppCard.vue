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
        <p>{{ app.protocol.toUpperCase() }} · 资源池 #{{ app.pool_id }}</p>
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
      <RouterLink class="app-card__link" :to="`/compute/pools/${app.pool_id}`" @click.stop>查看详情</RouterLink>
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
const launching = ref(false)
const errorMessage = ref('')

async function handleLaunch() {
  if (launching.value) {
    return
  }
  launching.value = true
  errorMessage.value = ''
  try {
    await launchRemoteApp(props.app.id, props.app.name, props.app.pool_id || 0)
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
  border: 1px solid #dbe3ef;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  cursor: pointer;
}

.app-card__header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

h2 {
  margin: 0 0 8px;
  font-size: 20px;
  color: #0f172a;
}

p {
  margin: 0;
  color: #64748b;
}

.app-card__status {
  align-self: start;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 13px;
}

.app-card__status--success {
  background: #dcfce7;
  color: #166534;
}

.app-card__status--warning {
  background: #fef3c7;
  color: #92400e;
}

.app-card__status--danger {
  background: #fee2e2;
  color: #991b1b;
}

.app-card__status--info,
.app-card__status--neutral {
  background: #e2e8f0;
  color: #334155;
}

.app-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #475569;
  font-size: 14px;
}

.app-card__meta span {
  padding: 4px 9px;
  border-radius: 999px;
  background: #f1f5f9;
}

.app-card__link {
  color: #1d4ed8;
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
  color: #475569;
  font-size: 14px;
}

.app-card__error {
  margin: 0;
  color: #b91c1c;
  font-size: 14px;
}
</style>
