import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getCaseDetail, getCaseList, transferCase } from '@/modules/cases/services/api/cases'
import type { CaseDetail, CaseListItem, CaseTransferResponse } from '@/modules/cases/types/cases'

function normalizeKeyword(value: string) {
  return value.trim().toLowerCase()
}

export const useCasesStore = defineStore('cases', () => {
  const items = ref<CaseListItem[]>([])
  const loaded = ref(false)
  const loading = ref(false)
  const errorMessage = ref('')
  const keyword = ref('')

  const detail = ref<CaseDetail | null>(null)
  const detailLoading = ref(false)
  const detailErrorMessage = ref('')
  const transferLoading = ref(false)
  const transferResult = ref<CaseTransferResponse | null>(null)

  const filteredItems = computed(() => {
    const normalizedKeyword = normalizeKeyword(keyword.value)
    if (!normalizedKeyword) {
      return items.value
    }

    return items.value.filter((item) => {
      const haystack = `${item.title} ${item.summary} ${item.case_uid}`.toLowerCase()
      return haystack.includes(normalizedKeyword)
    })
  })

  async function loadList(force = false) {
    if (loaded.value && !force) {
      return
    }

    loading.value = true
    errorMessage.value = ''
    try {
      const response = await getCaseList()
      items.value = response.data
      loaded.value = true
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载案例列表失败'
    } finally {
      loading.value = false
    }
  }

  async function openDetail(caseId: number) {
    detailLoading.value = true
    detailErrorMessage.value = ''
    transferResult.value = null
    try {
      const response = await getCaseDetail(caseId)
      detail.value = response.data
    } catch (error) {
      detail.value = null
      detailErrorMessage.value = error instanceof Error ? error.message : '加载案例详情失败'
    } finally {
      detailLoading.value = false
    }
  }

  async function transferCurrentCase() {
    if (!detail.value) {
      return
    }

    transferLoading.value = true
    detailErrorMessage.value = ''
    transferResult.value = null
    try {
      const response = await transferCase(detail.value.id)
      transferResult.value = response.data
    } catch (error) {
      detailErrorMessage.value = error instanceof Error ? error.message : '转存案例失败'
    } finally {
      transferLoading.value = false
    }
  }

  return {
    detail,
    detailErrorMessage,
    detailLoading,
    errorMessage,
    filteredItems,
    items,
    keyword,
    loaded,
    loading,
    transferLoading,
    transferResult,
    loadList,
    openDetail,
    transferCurrentCase,
  }
})
