import http from '@/services/http'

import type { AdminAnalyticsOverviewResponse } from '@/modules/admin/types/analytics'

export function getAdminAnalyticsOverview() {
  return http.get<AdminAnalyticsOverviewResponse>('/api/admin/analytics/overview')
}
