<template>
  <div class="portal-shell">
    <PortalSidebar />
    <main class="portal-shell__main">
      <PortalTopbar />
      <PortalBreadcrumb />
      <section class="portal-shell__content">
        <RouterView />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'

import PortalBreadcrumb from './PortalBreadcrumb.vue'
import PortalSidebar from './PortalSidebar.vue'
import PortalTopbar from './PortalTopbar.vue'
</script>

<style scoped>
.portal-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 248px 1fr;
  background: #eef3fb;
}

.portal-shell__main {
  display: grid;
  grid-template-rows: auto auto 1fr;
}

.portal-shell__content {
  padding: 24px;
}
</style>
