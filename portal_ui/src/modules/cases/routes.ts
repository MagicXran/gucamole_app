import type { RouteRecordRaw } from 'vue-router'

import CaseDetailView from '@/modules/cases/views/CaseDetailView.vue'
import CaseListView from '@/modules/cases/views/CaseListView.vue'

export const caseRoutes: RouteRecordRaw[] = [
  {
    path: '/cases',
    component: CaseListView,
  },
  {
    path: '/cases/:caseId',
    component: CaseDetailView,
  },
]
