import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getSdkPackageDetail, getSdkPackages } from '@/modules/sdk/services/api/sdk'
import type { SdkPackageDetail, SdkPackageKind, SdkPackageListItem } from '@/modules/sdk/types/sdk'

function normalizeKeyword(value: string) {
  return value.trim().toLowerCase()
}

export const useSdkStore = defineStore('sdk', () => {
  const packageKind = ref<SdkPackageKind>('cloud_platform')
  const packages = ref<SdkPackageListItem[]>([])
  const detailsById = ref<Record<number, SdkPackageDetail>>({})
  const selectedPackageId = ref<number | null>(null)
  const keywordByKind = ref<Record<SdkPackageKind, string>>({
    cloud_platform: '',
    simulation_app: '',
  })
  const loading = ref(false)
  const detailLoading = ref(false)
  const errorMessage = ref('')
  const detailErrorMessage = ref('')
  const packageRequestId = ref(0)
  const detailRequestId = ref(0)

  const keyword = computed({
    get() {
      return keywordByKind.value[packageKind.value] || ''
    },
    set(value: string) {
      keywordByKind.value = {
        ...keywordByKind.value,
        [packageKind.value]: value,
      }
    },
  })

  const filteredPackages = computed(() => {
    const normalizedKeyword = normalizeKeyword(keyword.value)
    if (!normalizedKeyword) {
      return packages.value
    }

    return packages.value.filter((item) => {
      const haystack = `${item.name} ${item.summary}`.toLowerCase()
      return haystack.includes(normalizedKeyword)
    })
  })

  const selectedDetail = computed(() => {
    if (!selectedPackageId.value) {
      return null
    }
    return detailsById.value[selectedPackageId.value] || null
  })

  async function loadPackages(nextKind: SdkPackageKind) {
    const requestId = packageRequestId.value + 1
    packageRequestId.value = requestId
    packageKind.value = nextKind
    loading.value = true
    errorMessage.value = ''
    detailErrorMessage.value = ''
    detailRequestId.value += 1
    detailLoading.value = false
    packages.value = []
    detailsById.value = {}
    selectedPackageId.value = null

    try {
      const response = await getSdkPackages(nextKind)
      if (requestId !== packageRequestId.value || packageKind.value !== nextKind) {
        return
      }

      packages.value = response.data
      const firstPackage = response.data[0]
      if (firstPackage) {
        await selectPackage(firstPackage.id, nextKind)
      }
    } catch (error) {
      if (requestId !== packageRequestId.value || packageKind.value !== nextKind) {
        return
      }

      packages.value = []
      errorMessage.value = error instanceof Error ? error.message : '加载 SDK 列表失败'
    } finally {
      if (requestId === packageRequestId.value && packageKind.value === nextKind) {
        loading.value = false
      }
    }
  }

  async function selectPackage(packageId: number, expectedKind = packageKind.value) {
    selectedPackageId.value = packageId
    detailErrorMessage.value = ''

    if (detailsById.value[packageId]) {
      detailLoading.value = false
      return
    }

    const requestId = detailRequestId.value + 1
    detailRequestId.value = requestId
    detailLoading.value = true
    try {
      const response = await getSdkPackageDetail(packageId)
      if (
        requestId !== detailRequestId.value ||
        packageKind.value !== expectedKind ||
        selectedPackageId.value !== packageId
      ) {
        return
      }

      detailsById.value = {
        ...detailsById.value,
        [packageId]: response.data,
      }
    } catch (error) {
      if (
        requestId !== detailRequestId.value ||
        packageKind.value !== expectedKind ||
        selectedPackageId.value !== packageId
      ) {
        return
      }

      detailErrorMessage.value = error instanceof Error ? error.message : '加载 SDK 版本失败'
    } finally {
      if (
        requestId === detailRequestId.value &&
        packageKind.value === expectedKind &&
        selectedPackageId.value === packageId
      ) {
        detailLoading.value = false
      }
    }
  }

  return {
    detailErrorMessage,
    detailLoading,
    errorMessage,
    filteredPackages,
    keyword,
    loading,
    packageKind,
    packages,
    selectedDetail,
    selectedPackageId,
    loadPackages,
    selectPackage,
  }
})
