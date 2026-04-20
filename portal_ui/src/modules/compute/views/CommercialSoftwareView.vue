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
      <AppCard v-for="app in commercialApps" :key="app.pool_id" :app="app" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'

import AppCard from '@/modules/compute/components/AppCard.vue'
import AppFilterBar from '@/modules/compute/components/AppFilterBar.vue'
import { useComputeStore } from '@/stores/compute'

const computeStore = useComputeStore()
const commercialApps = computed(() =>
  computeStore.filteredApps.filter((app) => !app.app_kind || app.app_kind === 'commercial_software'),
)

onMounted(() => {
  if (computeStore.apps.length === 0) {
    void computeStore.loadApps()
  }
})
</script>

<style scoped>
.commercial-view {
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.commercial-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
}

.commercial-view__empty,
.commercial-view__error {
  padding: 32px;
  border-radius: 14px;
  background: #f8fafc;
  color: #64748b;
}

.commercial-view__error {
  color: #b91c1c;
  background: #fef2f2;
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
