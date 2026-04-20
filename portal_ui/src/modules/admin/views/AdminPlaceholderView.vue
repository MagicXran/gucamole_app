<template>
  <section class="admin-placeholder-view">
    <h1>{{ title }}</h1>
    <p>{{ description }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useNavigationStore } from '@/stores/navigation'

const route = useRoute()
const navigationStore = useNavigationStore()

const title = computed(() => {
  return navigationStore.resolveBreadcrumb(route.path).at(-1) || '系统管理'
})

const description = computed(() => {
  return 'Vue 管理工作台正在接管这个运营入口。'
})
</script>

<style scoped>
.admin-placeholder-view {
  display: grid;
  gap: 10px;
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.admin-placeholder-view h1,
.admin-placeholder-view p {
  margin: 0;
}
</style>
