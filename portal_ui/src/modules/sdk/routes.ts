import type { RouteRecordRaw } from 'vue-router'

import CloudSdkView from '@/modules/sdk/views/CloudSdkView.vue'
import SimulationAppSdkView from '@/modules/sdk/views/SimulationAppSdkView.vue'

export const sdkRoutes: RouteRecordRaw[] = [
  {
    path: '/sdk/cloud',
    component: CloudSdkView,
  },
  {
    path: '/sdk/simulation-app',
    component: SimulationAppSdkView,
  },
]
