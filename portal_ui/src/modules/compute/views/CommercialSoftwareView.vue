<template>
  <section class="commercial-view">
    <header>
      <h1>可用软件列表</h1>
      <p>展示当前账号可访问的商业软件资源池。</p>
    </header>

    <AppFilterBar v-model="computeStore.query" />

    <div v-if="computeStore.errorMessage" class="commercial-view__error">
      {{ computeStore.errorMessage }}
    </div>
    <div v-else-if="computeStore.loading" class="commercial-view__empty">加载中...</div>
    <div v-else-if="commercialApps.length === 0" class="commercial-view__empty">暂无可用软件</div>
    <div v-else class="commercial-view__grid">
      <AppCard v-for="app in commercialApps" :key="app.capacity_pool_id ?? app.pool_id ?? app.runtime_id ?? app.id" :app="app" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import AppCard from '@/modules/compute/components/AppCard.vue'
import AppFilterBar from '@/modules/compute/components/AppFilterBar.vue'
import { useComputeAutoRefresh } from '@/modules/compute/composables/useComputeAutoRefresh'
import { useComputeStore } from '@/stores/compute'

const computeStore = useComputeStore()
const commercialApps = computed(() =>
  computeStore.filteredApps.filter((app) => !app.app_kind || app.app_kind === 'commercial_software'),
)
useComputeAutoRefresh(computeStore)
</script>

<style scoped>
.commercial-view {
  padding: 24px;
  background: var(--portal-color-surface);
  border: 1px solid var(--portal-color-border);
  border-radius: 24px;
  box-shadow: var(--portal-shadow-soft);
}

.commercial-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
}

.commercial-view__empty,
.commercial-view__error {
  padding: 32px;
  border-radius: 18px;
  background: var(--portal-color-surface-soft);
  color: var(--portal-color-body);
}

.commercial-view__error {
  color: var(--portal-color-danger);
  background: #fff5f7;
}

h1 {
  margin: 0 0 12px;
  font-size: 32px;
  color: var(--portal-color-ink);
  letter-spacing: -0.02em;
}

p {
  margin: 0;
  color: var(--portal-color-body);
}
</style>
