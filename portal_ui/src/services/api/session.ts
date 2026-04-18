import http from '@/services/http'
import type { SessionBootstrapPayload } from '@/types/auth'

export function getSessionBootstrap() {
  return http.get<SessionBootstrapPayload>('/api/session/bootstrap')
}
