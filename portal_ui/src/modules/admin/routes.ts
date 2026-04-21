import type { RouteRecordRaw } from 'vue-router'

import AdminAclView from '@/modules/admin/views/AdminAclView.vue'
import AdminAnalyticsView from '@/modules/admin/views/AdminAnalyticsView.vue'
import AdminAuditView from '@/modules/admin/views/AdminAuditView.vue'
import AdminAppsView from '@/modules/admin/views/AdminAppsView.vue'
import AdminDashboardView from '@/modules/admin/views/AdminDashboardView.vue'
import AdminMonitorView from '@/modules/admin/views/AdminMonitorView.vue'
import AdminPoolsView from '@/modules/admin/views/AdminPoolsView.vue'
import AdminQueuesView from '@/modules/admin/views/AdminQueuesView.vue'
import AdminUsersView from '@/modules/admin/views/AdminUsersView.vue'
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
    path: '/admin/pools',
    component: AdminPoolsView,
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
    path: '/admin/users',
    component: AdminUsersView,
    meta: {
      requiresAdmin: true,
    },
  },
  {
    path: '/admin/acl',
    component: AdminAclView,
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
  {
    path: '/admin/audit',
    component: AdminAuditView,
    meta: {
      requiresAdmin: true,
    },
  },
]
