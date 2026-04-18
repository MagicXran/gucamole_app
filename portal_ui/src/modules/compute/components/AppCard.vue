<template>
  <article class="app-card">
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

    <RouterLink class="app-card__link" :to="`/compute/pools/${app.pool_id}`">查看详情</RouterLink>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { ComputeAppCard } from '@/types/compute'

const props = defineProps<{
  app: ComputeAppCard
}>()

const statusToneClass = computed(() => `app-card__status--${props.app.resource_status_tone || 'neutral'}`)
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
</style>
