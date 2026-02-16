import axios from 'axios'

const RAW_BASE = (import.meta as any)?.env?.VITE_API_BASE || 'http://127.0.0.1:8000'
const baseURL = String(RAW_BASE).replace(/\/$/, '')

let loggedOnce = false

export const api = axios.create({ baseURL })

api.interceptors.request.use((config) => {
  const hasApiInBase = /\/api$/i.test(baseURL)
  if (config.url && hasApiInBase && config.url.startsWith('/api/')) {
    config.url = config.url.replace(/^\/api/, '')
  }

  if (!loggedOnce && (import.meta as any)?.env?.DEV) {
    const final = `${config.baseURL || ''}${config.url || ''}`
    // one-time request URL log for routing diagnostics
    console.info('[api] first request URL:', final)
    loggedOnce = true
  }
  return config
})
