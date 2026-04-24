import { onMounted } from 'vue'

type ComputeStoreLike = {
  loading: boolean
  refreshing?: boolean
  refreshApps: () => Promise<unknown>
}

export function useComputeAutoRefresh(store: ComputeStoreLike) {
  const isRefreshing = () => store.loading || Boolean(store.refreshing)

  onMounted(() => {
    if (!isRefreshing()) {
      void store.refreshApps()
    }
  })
}
