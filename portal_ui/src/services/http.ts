import axios, { AxiosHeaders } from 'axios'

import { PORTAL_TOKEN_KEY } from '@/constants/auth'

const http = axios.create({
  baseURL: '/',
  headers: {
    'Content-Type': 'application/json',
  },
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(PORTAL_TOKEN_KEY)

  if (token) {
    if (typeof config.headers?.set === 'function') {
      config.headers.set('Authorization', `Bearer ${token}`)
    } else {
      config.headers = AxiosHeaders.from({
        ...config.headers,
        Authorization: `Bearer ${token}`,
      })
    }
  }

  return config
})

http.interceptors.response.use((response) => {
  const nextToken =
    typeof response.headers?.get === 'function'
      ? response.headers.get('refresh-token')
      : response.headers?.['refresh-token']

  if (typeof nextToken === 'string' && nextToken) {
    localStorage.setItem(PORTAL_TOKEN_KEY, nextToken)
  }

  return response
})

export default http
