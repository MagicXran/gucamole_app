<template>
  <nav class="breadcrumb">
    <template v-for="(item, index) in breadcrumb" :key="item">
      <span>{{ item }}</span>
      <span v-if="index < breadcrumb.length - 1" class="breadcrumb__sep">/</span>
    </template>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useNavigationStore } from '@/stores/navigation'

const route = useRoute()
const navigationStore = useNavigationStore()
const breadcrumb = computed(() => navigationStore.resolveBreadcrumb(route.path))
</script>

<style scoped>
.breadcrumb {
  padding: 16px 24px;
  color: #334155;
  background: rgba(255, 255, 255, 0.72);
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.breadcrumb__sep {
  margin: 0 6px;
  color: #94a3b8;
}
</style>
