import type { RouteRecordRaw } from 'vue-router'

import AppTasksView from '@/modules/my/views/AppTasksView.vue'
import BookingRegisterView from '@/modules/my/views/BookingRegisterView.vue'
import WorkspaceView from '@/modules/my/views/WorkspaceView.vue'

export const myRoutes: RouteRecordRaw[] = [
  {
    path: '/my/workspace',
    component: WorkspaceView,
  },
  {
    path: '/my/tasks',
    component: AppTasksView,
  },
  {
    path: '/my/bookings',
    component: BookingRegisterView,
  },
]
