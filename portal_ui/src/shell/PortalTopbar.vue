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
  background: #28539c;
  color: #fff;
}

.topbar__title {
  font-weight: 700;
}

.topbar__actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.topbar__link {
  color: #fff;
  text-decoration: none;
}

.topbar__logout {
  padding: 6px 10px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 999px;
  background: transparent;
  color: #fff;
  cursor: pointer;
}
</style>
