import axios from 'axios'

const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const api = axios.create({ baseURL: apiBaseUrl })

export const scanData = async (files) => {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await api.post('/api/scan', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  return data
}

export const trainModel = async (payload) => {
  const { data } = await api.post('/api/train', payload)
  return data
}

export const getImportance = async (modelId) => {
  const { data } = await api.get(`/api/train/${modelId}/importance`)
  return data
}

export const optimize = async (payload) => {
  const { data } = await api.post('/api/optimize/run', payload)
  return data
}

export const getModelHistory = async () => {
  const { data } = await api.get('/api/train/registry')
  return data
}

export const saveRun = async (runId) => {
  const { data } = await api.post('/api/train/save', { run_id: runId })
  return data
}

export const downloadArtifactUrl = (runId) => `${api.defaults.baseURL}/api/train/artifact/${runId}`

export default api
