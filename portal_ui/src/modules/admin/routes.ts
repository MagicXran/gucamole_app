import type { RouteRecordRaw } from 'vue-router'

import AdminAnalyticsView from '@/modules/admin/views/AdminAnalyticsView.vue'
import AdminAppsView from '@/modules/admin/views/AdminAppsView.vue'
import AdminDashboardView from '@/modules/admin/views/AdminDashboardView.vue'
import AdminMonitorView from '@/modules/admin/views/AdminMonitorView.vue'
import AdminQueuesView from '@/modules/admin/views/AdminQueuesView.vue'
import AdminWorkersView from '@/modules/admin/views/AdminWorkersView.vue'

export const adminRoutes: RouteRecordRaw[] = [
  {
    path: '/admin',
    component: AdminDashboardView,
    meta: {
      requiresAdmin: true,
    },
  },
  {
    path: '/admin/analytics',
    component: AdminAnalyticsView,
    meta: {
      requiresAdmin: true,
    },
  },
  {
    path: '/admin/apps',
    component: AdminAppsView,
    meta: {
      requiresAdmin: true,
    },
  },
  {
    path: '/admin/queues',
    component: AdminQueuesView,
    meta: {
      requiresAdmin: true,
    },
  },
  {
    path: '/admin/monitor',
    component: AdminMonitorView,
    meta: {
      requiresAdmin: true,
    },
  },
  {
    path: '/admin/workers',
    component: AdminWorkersView,
    meta: {
      requiresAdmin: true,
    },
  },
]
