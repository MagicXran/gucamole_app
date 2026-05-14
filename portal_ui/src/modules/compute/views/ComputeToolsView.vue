<template>
  <section class="compute-view">
    <header>
      <h1>计算工具列表</h1>
      <p>展示当前账号可访问的计算工具资源。</p>
    </header>

    <AppFilterBar v-model="computeStore.query" />

    <div v-if="computeStore.loading" class="compute-view__state">加载中...</div>
    <div v-else-if="computeStore.errorMessage" class="compute-view__state compute-view__state--error">{{ computeStore.errorMessage }}</div>
    <div v-else-if="items.length === 0" class="compute-view__state">暂无计算工具</div>
    <div v-else class="compute-view__grid">
      <AppCard v-for="app in items" :key="app.capacity_pool_id ?? app.pool_id ?? app.runtime_id ?? app.id" :app="app" />
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
const items = computed(() => computeStore.filteredApps.filter((app) => app.app_kind === 'compute_tool'))
useComputeAutoRefresh(computeStore)
</script>

<style scoped>
.compute-view {
  padding: 24px;
  background: var(--portal-color-surface);
  border: 1px solid var(--portal-color-border);
  border-radius: 24px;
  box-shadow: var(--portal-shadow-soft);
}

.compute-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
}

.compute-view__state {
  padding: 32px;
  border-radius: 18px;
  background: var(--portal-color-surface-soft);
  color: var(--portal-color-body);
}

.compute-view__state--error {
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
