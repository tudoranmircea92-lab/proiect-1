import { api } from './api'

export async function runJob(startPath: string, payload: any, onProgress: (s: {progress:number; stage:string; status:string}) => void) {
  const start = await api.post(startPath, payload)
  const jobId = start.data.job_id
  while (true) {
    const res = await api.get(`/api/jobs/${jobId}`)
    const j = res.data
    onProgress({ progress: j.progress ?? 0, stage: j.stage ?? '', status: j.status })
    if (j.status === 'done') return j.result
    if (j.status === 'error') throw new Error(j.error || 'Job failed')
    await new Promise(r => setTimeout(r, 400))
  }
}

export async function runUploadJob(form: FormData, onProgress: (s: {progress:number; stage:string; status:string}) => void) {
  const start = await api.post('/api/data/upload', form)
  const jobId = start.data.job_id
  while (true) {
    const res = await api.get(`/api/jobs/${jobId}`)
    const j = res.data
    onProgress({ progress: j.progress ?? 0, stage: j.stage ?? '', status: j.status })
    if (j.status === 'done') return j.result
    if (j.status === 'error') throw new Error(j.error || 'Job failed')
    await new Promise(r => setTimeout(r, 400))
  }
}


export async function runJobWithMeta(startPath: string, payload: any, onProgress: (s: {progress:number; stage:string; status:string}) => void) {
  const start = await api.post(startPath, payload)
  const jobId = start.data.job_id
  while (true) {
    const res = await api.get(`/api/jobs/${jobId}`)
    const j = res.data
    onProgress({ progress: j.progress ?? 0, stage: j.stage ?? '', status: j.status })
    if (j.status === 'done') return { jobId, result: j.result }
    if (j.status === 'error') throw new Error(j.error || 'Job failed')
    await new Promise(r => setTimeout(r, 400))
  }
}


export async function waitForJob(jobId: string, onProgress: (s: {progress:number; stage:string; status:string}) => void) {
  while (true) {
    const res = await api.get(`/api/jobs/${jobId}`)
    const j = res.data
    onProgress({ progress: j.progress ?? 0, stage: j.stage ?? '', status: j.status })
    if (j.status === 'done') return j.result
    if (j.status === 'error') throw new Error(j.error || 'Job failed')
    await new Promise(r => setTimeout(r, 400))
  }
}
