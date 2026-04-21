import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  createAdminWorkerGroup,
  createAdminWorkerNode,
  issueAdminWorkerEnrollment,
  listAdminWorkerGroups,
  listAdminWorkerNodes,
  revokeAdminWorkerNode,
  rotateAdminWorkerToken,
} from '@/modules/admin/services/api/ops'
import type {
  AdminWorkerEnrollmentResponse,
  AdminWorkerGroup,
  AdminWorkerGroupCreatePayload,
  AdminWorkerNode,
  AdminWorkerNodeCreatePayload,
  AdminWorkerTokenResponse,
} from '@/modules/admin/types/ops'

export const useAdminWorkersStore = defineStore('admin-workers', () => {
  const groups = ref<AdminWorkerGroup[]>([])
  const nodes = ref<AdminWorkerNode[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const errorMessage = ref('')

  async function loadWorkers() {
    loading.value = true
    errorMessage.value = ''
    try {
      const [groupsResponse, nodesResponse] = await Promise.all([
        listAdminWorkerGroups(),
        listAdminWorkerNodes(),
      ])
      groups.value = groupsResponse.data.items || []
      nodes.value = nodesResponse.data.items || []
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载 Worker 状态失败'
      groups.value = []
      nodes.value = []
    } finally {
      loading.value = false
    }
  }

  async function saveWorkerGroup(payload: AdminWorkerGroupCreatePayload) {
    saving.value = true
    errorMessage.value = ''
    try {
      await createAdminWorkerGroup(payload)
      await loadWorkers()
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '创建节点组失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  async function saveWorkerNode(payload: AdminWorkerNodeCreatePayload) {
    saving.value = true
    errorMessage.value = ''
    try {
      await createAdminWorkerNode(payload)
      await loadWorkers()
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '创建 Worker 节点失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  async function issueEnrollment(workerNodeId: number): Promise<AdminWorkerEnrollmentResponse> {
    saving.value = true
    errorMessage.value = ''
    try {
      const response = await issueAdminWorkerEnrollment(workerNodeId, { expires_hours: 24 })
      await loadWorkers()
      return response.data
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '签发注册码失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  async function rotateToken(workerNodeId: number): Promise<AdminWorkerTokenResponse> {
    saving.value = true
    errorMessage.value = ''
    try {
      const response = await rotateAdminWorkerToken(workerNodeId)
      await loadWorkers()
      return response.data
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '轮换凭证失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  async function revokeNode(workerNodeId: number) {
    saving.value = true
    errorMessage.value = ''
    try {
      await revokeAdminWorkerNode(workerNodeId)
      await loadWorkers()
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '吊销 Worker 节点失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  return {
    groups,
    nodes,
    loading,
    saving,
    errorMessage,
    loadWorkers,
    saveWorkerGroup,
    saveWorkerNode,
    issueEnrollment,
    rotateToken,
    revokeNode,
  }
})
