import { request } from './client'

export async function health() {
  const { body, url } = await request('/api/plasma/health')
  return { data: body, url }
}

export async function columns() {
  const { body, url } = await request('/api/plasma/columns')
  return { data: body, url }
}

export async function stability(payload: any) {
  const { body, url } = await request('/api/plasma/stability', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return { data: body, url }
}

export async function exportCsv(query: string) {
  const { res, url } = await request(`/api/plasma/stability/export?${query}`)
  const blob = await res.blob()
  return { blob, url }
}


export async function stabilityV2(payload: any) {
  const { body, url } = await request('/api/plasma/stability_v2', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return { data: body, url }
}
