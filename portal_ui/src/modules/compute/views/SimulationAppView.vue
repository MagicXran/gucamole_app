<template>
  <section class="compute-view">
    <header>
      <h1>仿真应用列表</h1>
      <p>展示当前账号可访问的仿真APP资源。</p>
    </header>

    <AppFilterBar v-model="computeStore.query" />

    <div v-if="computeStore.loading" class="compute-view__state">加载中...</div>
    <div v-else-if="computeStore.errorMessage" class="compute-view__state compute-view__state--error">{{ computeStore.errorMessage }}</div>
    <div v-else-if="items.length === 0" class="compute-view__state">暂无仿真应用</div>
    <div v-else class="compute-view__grid">
      <AppCard v-for="app in items" :key="app.pool_id" :app="app" />
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
const items = computed(() => computeStore.filteredApps.filter((app) => app.app_kind === 'simulation_app'))
useComputeAutoRefresh(computeStore)
</script>

<style scoped>
.compute-view {
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.compute-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
}

.compute-view__state {
  padding: 32px;
  border-radius: 14px;
  background: #f8fafc;
  color: #64748b;
}

.compute-view__state--error {
  color: #b91c1c;
}

h1 {
  margin: 0 0 12px;
  font-size: 32px;
  color: #1e3a8a;
}

p {
  margin: 0;
  color: #475569;
}
</style>
