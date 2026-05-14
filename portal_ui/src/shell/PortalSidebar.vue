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
  background: var(--portal-color-sidebar);
  color: #a8acb3;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
}

.sidebar__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px 18px;
  margin-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.sidebar__logo {
  width: 38px;
  height: 38px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: var(--portal-color-primary);
  color: #fff;
  font-weight: 700;
}

.sidebar__brand-title {
  color: #fff;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.sidebar__brand-subtitle {
  font-size: 12px;
  color: var(--portal-color-muted);
}

.sidebar__group-title {
  padding: 10px 12px;
  color: #fff;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.sidebar__group-title--link {
  display: block;
  color: inherit;
  text-decoration: none;
}

.sidebar__group-title--active {
  color: #7aa6ff;
}

.sidebar__item {
  display: block;
  margin-left: 14px;
  padding: 10px 12px;
  border-left: 2px solid transparent;
  border-radius: 12px;
  color: inherit;
  text-decoration: none;
  transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}

.sidebar__item:hover {
  background: var(--portal-color-sidebar-hover);
  color: #f5f7fb;
}

.sidebar__item--active {
  border-left-color: var(--portal-color-primary);
  background: rgba(0, 82, 255, 0.14);
  color: #dce7ff;
}
</style>
