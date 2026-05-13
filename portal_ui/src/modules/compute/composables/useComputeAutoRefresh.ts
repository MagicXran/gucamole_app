import { onMounted, onUnmounted } from 'vue'

type ComputeStoreLike = {
  loading: boolean
  refreshing?: boolean
  refreshApps: () => Promise<unknown>
}

const COMPUTE_LAUNCH_EVENT = 'portal-compute-launch'

export function useComputeAutoRefresh(store: ComputeStoreLike) {
  const isRefreshing = () => store.loading || Boolean(store.refreshing)
  const handleLaunchRefresh = () => {
    if (!isRefreshing()) {
      void store.refreshApps()
    }
  }

  onMounted(() => {
    if (!isRefreshing()) {
      void store.refreshApps()
    }
    window.addEventListener(COMPUTE_LAUNCH_EVENT, handleLaunchRefresh)
  })

  onUnmounted(() => {
    window.removeEventListener(COMPUTE_LAUNCH_EVENT, handleLaunchRefresh)
  })
}
