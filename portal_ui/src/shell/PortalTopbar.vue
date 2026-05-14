<template>
  <header class="topbar">
    <div class="topbar__title">南钢-仿真</div>
    <div class="topbar__actions">
      <a class="topbar__link" href="/portal/my/workspace">结果中心</a>
      <div class="topbar__user">{{ displayName }}</div>
      <form action="/login.html" method="get">
        <button class="topbar__logout" type="submit" data-testid="portal-logout" @click="logout">退出</button>
      </form>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { PORTAL_TOKEN_KEY, PORTAL_USER_KEY } from '@/constants/auth'
import { useSessionStore } from '@/stores/session'

const sessionStore = useSessionStore()
const displayName = computed(() => sessionStore.user?.display_name || sessionStore.user?.username || '未登录')

function logout() {
  localStorage.removeItem(PORTAL_TOKEN_KEY)
  localStorage.removeItem(PORTAL_USER_KEY)
}
</script>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--portal-color-ink);
  border-bottom: 1px solid var(--portal-color-border);
  backdrop-filter: blur(10px);
}

.topbar__title {
  font-weight: 700;
  letter-spacing: 0.08em;
}

.topbar__actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.topbar__link {
  color: var(--portal-color-body);
  text-decoration: none;
  font-weight: 500;
}

.topbar__link:hover {
  color: var(--portal-color-primary);
}

.topbar__user {
  padding: 8px 14px;
  border-radius: 999px;
  background: var(--portal-color-surface-soft);
  color: var(--portal-color-ink);
  font-size: 14px;
}

.topbar__logout {
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--portal-color-border);
  border-radius: 999px;
  background: var(--portal-color-surface);
  color: var(--portal-color-ink);
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease;
}

.topbar__logout:hover {
  border-color: var(--portal-color-primary);
  color: var(--portal-color-primary);
}
</style>
