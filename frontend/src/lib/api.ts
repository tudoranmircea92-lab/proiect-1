import axios from 'axios'

const RAW_BASE = (import.meta as any)?.env?.VITE_API_BASE || 'http://127.0.0.1:8000'
const API_BASE = String(RAW_BASE).replace(/\/$/, '')

let loggedOnce = false

function normalizeApiPath(path: string) {
  if (!path) return path
  const hasApiInBase = /\/api$/i.test(API_BASE)
  if (hasApiInBase && path.startsWith('/api/')) {
    return path.replace(/^\/api/, '')
  }
  return path
}

export function resolveApiUrl(path: string): string {
  const normalizedPath = normalizeApiPath(path)
  if (/^https?:\/\//i.test(normalizedPath)) return normalizedPath
  return `${API_BASE}${normalizedPath}`
}

export { API_BASE }

export const api = axios.create({ baseURL: API_BASE })

api.interceptors.request.use((config) => {
  if (config.url) {
    config.url = normalizeApiPath(config.url)
    ;(config as any).__finalUrl = resolveApiUrl(config.url)
  }

  if (!loggedOnce && (import.meta as any)?.env?.DEV) {
    const final = (config as any).__finalUrl || `${config.baseURL || ''}${config.url || ''}`
    // one-time request URL log for routing diagnostics
    console.info('[api] first request URL:', final)
    loggedOnce = true
  }
  return config
})
