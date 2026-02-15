import axios from 'axios'

const api = axios.create({ baseURL: 'http://127.0.0.1:8000' })

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

export default api
