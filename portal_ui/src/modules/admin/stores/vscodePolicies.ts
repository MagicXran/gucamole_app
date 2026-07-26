import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  createVscodeControlProfile,
  deleteVscodeControlProfile,
  getVscodeControlCatalog,
  listVscodeControlProfiles,
  updateVscodeControlProfile,
} from '@/modules/admin/services/api/vscodePolicies'
import type {
  VscodeControlCatalog,
  VscodeControlProfile,
  VscodeControlProfilePayload,
} from '@/modules/admin/types/vscodePolicies'

export const useAdminVscodePoliciesStore = defineStore('admin-vscode-policies', () => {
  const catalog = ref<VscodeControlCatalog | null>(null)
  const profiles = ref<VscodeControlProfile[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const errorMessage = ref('')

  async function bootstrap() {
    loading.value = true
    errorMessage.value = ''
    try {
      const [catalogResponse, profilesResponse] = await Promise.all([
        getVscodeControlCatalog(),
        listVscodeControlProfiles(),
      ])
      catalog.value = catalogResponse.data
      profiles.value = profilesResponse.data.items
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载 VSCode 策略失败'
      profiles.value = []
    } finally {
      loading.value = false
    }
  }

  async function saveProfile(profileId: number | null, payload: VscodeControlProfilePayload) {
    saving.value = true
    errorMessage.value = ''
    try {
      const response = profileId
        ? await updateVscodeControlProfile(profileId, payload)
        : await createVscodeControlProfile(payload)
      await bootstrap()
      return response.data
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '保存 VSCode 策略失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  async function removeProfile(profileId: number) {
    saving.value = true
    errorMessage.value = ''
    try {
      await deleteVscodeControlProfile(profileId)
      await bootstrap()
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '删除 VSCode 策略失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  return {
    catalog,
    profiles,
    loading,
    saving,
    errorMessage,
    bootstrap,
    saveProfile,
    removeProfile,
  }
})
