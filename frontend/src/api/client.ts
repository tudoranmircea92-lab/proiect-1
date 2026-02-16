export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export type ApiErrorShape = {
  status: number
  url: string
  body: any
  message: string
}

export async function request(path: string, init: RequestInit = {}, timeoutMs = 15000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  const url = `${API_BASE_URL}${path}`
  try {
    const res = await fetch(url, { ...init, signal: controller.signal })
    const contentType = res.headers.get('content-type') || ''
    const body = contentType.includes('application/json') ? await res.json() : await res.text()
    if (!res.ok) {
      const err: ApiErrorShape = {
        status: res.status,
        url,
        body,
        message: typeof body === 'string' ? body : (body?.error?.message || `HTTP ${res.status}`),
      }
      throw err
    }
    return { res, body, url }
  } finally {
    clearTimeout(timer)
  }
}
