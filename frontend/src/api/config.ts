export { API_BASE_URL as API_BASE } from './client'

export function apiUrl(path: string) {
  const base = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
  return `${base}${path}`
}
