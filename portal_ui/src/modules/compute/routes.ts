import type { RouteRecordRaw } from 'vue-router'

import CommercialSoftwareView from './views/CommercialSoftwareView.vue'
import AppDetailView from './views/AppDetailView.vue'
import ComputeToolsView from './views/ComputeToolsView.vue'
import SimulationAppView from './views/SimulationAppView.vue'

export const computeRoutes: RouteRecordRaw[] = [
  {
    path: '/compute/commercial',
    component: CommercialSoftwareView,
  },
  {
    path: '/compute/simulation',
    component: SimulationAppView,
  },
  {
    path: '/compute/tools',
    component: ComputeToolsView,
  },
  {
    path: '/compute/pools/:poolId',
    component: AppDetailView,
  },
]
