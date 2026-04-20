<template>
  <aside class="sidebar">
    <div class="sidebar__brand">
      <div class="sidebar__logo">NG</div>
      <div>
        <div class="sidebar__brand-title">南京钢铁</div>
        <div class="sidebar__brand-subtitle">NANJING STEEL</div>
      </div>
    </div>
    <section v-for="group in menuTree" :key="group.key" class="sidebar__group">
      <RouterLink
        v-if="group.path"
        :to="group.path"
        class="sidebar__group-title sidebar__group-title--link"
        active-class="sidebar__group-title--active"
      >
        {{ group.title }}
      </RouterLink>
      <div v-else class="sidebar__group-title">{{ group.title }}</div>
      <RouterLink
        v-for="child in group.children || []"
        :key="child.key"
        :to="child.path || '/'"
        class="sidebar__item"
        active-class="sidebar__item--active"
      >
        {{ child.title }}
      </RouterLink>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { RouterLink } from 'vue-router'

import { useNavigationStore } from '@/stores/navigation'

const navigationStore = useNavigationStore()
const { menuTree } = storeToRefs(navigationStore)
</script>

<style scoped>
.sidebar {
  padding: 18px 14px;
  background: #111827;
  color: #cbd5e1;
}

.sidebar__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px 18px;
  margin-bottom: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.sidebar__logo {
  width: 38px;
  height: 38px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: #b91c1c;
  color: #fff;
  font-weight: 700;
}

.sidebar__brand-title {
  color: #fff;
  font-weight: 700;
}

.sidebar__brand-subtitle {
  font-size: 12px;
  color: #94a3b8;
}

.sidebar__group-title {
  padding: 10px 12px;
  color: #f8fafc;
  font-weight: 600;
}

.sidebar__group-title--link {
  display: block;
  color: inherit;
  text-decoration: none;
}

.sidebar__group-title--active {
  color: #93c5fd;
}

.sidebar__item {
  display: block;
  margin-left: 14px;
  padding: 10px 12px;
  border-left: 3px solid transparent;
  color: inherit;
  text-decoration: none;
}

.sidebar__item--active {
  border-left-color: #60a5fa;
  background: #183154;
  color: #93c5fd;
}
</style>
