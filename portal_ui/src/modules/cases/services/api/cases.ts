import http from '@/services/http'

import type { CaseDetail, CaseListItem, CaseTransferResponse } from '@/modules/cases/types/cases'

export function getCaseList() {
  return http.get<CaseListItem[]>('/api/cases')
}

export function getCaseDetail(caseId: number) {
  return http.get<CaseDetail>(`/api/cases/${caseId}`)
}

export function transferCase(caseId: number) {
  return http.post<CaseTransferResponse>(`/api/cases/${caseId}/transfer`)
}
