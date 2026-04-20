export type AdminAnalyticsOverviewTotals = {
  software_launches: number
  case_events: number
  active_users: number
  department_count: number
}

export type AdminAnalyticsSoftwareRankItem = {
  app_id: number
  app_name: string
  launch_count: number
}

export type AdminAnalyticsCaseRankItem = {
  case_id: number
  case_uid: string
  case_title: string
  detail_count: number
  download_count: number
  transfer_count: number
  event_count: number
}

export type AdminAnalyticsUserRankItem = {
  user_id: number
  username: string
  display_name: string
  department: string
  software_launch_count: number
  case_event_count: number
  event_count: number
}

export type AdminAnalyticsDepartmentRankItem = {
  department: string
  user_count: number
  event_count: number
}

export type AdminAnalyticsOverviewResponse = {
  overview: AdminAnalyticsOverviewTotals
  software_ranking: AdminAnalyticsSoftwareRankItem[]
  case_ranking: AdminAnalyticsCaseRankItem[]
  user_ranking: AdminAnalyticsUserRankItem[]
  department_ranking: AdminAnalyticsDepartmentRankItem[]
}
