import { apiUrl } from './config'

export async function plasmaHealth() {
  const url = apiUrl('/api/plasma/health')
  const res = await fetch(url)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(body || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function plasmaStability(payload: any) {
  const url = apiUrl('/api/plasma/stability')
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(body || `HTTP ${res.status}`)
  }
  return res.json()
}
