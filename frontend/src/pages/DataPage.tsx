import { useRef, useState } from 'react'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'

type LoadResp = {
  dataset_id: string
  saved_path?: string
  rows: number
  columns: number
  preview: Record<string, unknown>[]
  grouped_columns: Record<string, string[]>
  missing_summary: Record<string, number>
  debug?: Record<string, unknown>
}

export function DataPage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [path, setPath] = useState('')
  const [format, setFormat] = useState<'auto' | 'csv' | 'parquet'>('auto')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [data, setData] = useState<LoadResp | null>(null)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [loadingUpload, setLoadingUpload] = useState(false)
  const [loadingPath, setLoadingPath] = useState(false)
  const { setDatasetId, setDatasetPath, datasetId } = useDataset()

  const uploadProfile = async () => {
    if (!selectedFile) return
    setLoadingUpload(true)
    setError('')
    setToast('')
    try {
      const form = new FormData()
      form.append('file', selectedFile)
      form.append('format', format)
      const res = await api.post('/api/data/upload', form)
      setData(res.data.profile)
      setDatasetId(res.data.dataset_id)
      setDatasetPath(res.data.saved_path)
      setToast(`Dataset uploaded successfully (id: ${res.data.dataset_id})`)
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Upload failed')
    } finally {
      setLoadingUpload(false)
    }
  }

  const loadFromPath = async () => {
    setLoadingPath(true)
    setError('')
    setToast('')
    try {
      const res = await api.post('/api/data/load', { path, format })
      setData(res.data)
      setDatasetId(res.data.dataset_id)
      setDatasetPath(res.data.saved_path ?? path)
      setToast(`Dataset loaded successfully (id: ${res.data.dataset_id})`)
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Failed to load data')
    } finally {
      setLoadingPath(false)
    }
  }

  const groups = data?.grouped_columns ?? {}
  const previewColumns = data?.preview?.length ? Object.keys(data.preview[0]) : []

  return (
    <div className="space-y-4">
      <section className="card space-y-3">
        <h2 className="text-lg font-semibold">Data</h2>
        {toast && <div className="text-emerald-700 bg-emerald-50 border border-emerald-200 rounded p-2 text-sm">✅ {toast}</div>}
        {error && <div className="text-red-700 bg-red-50 border border-red-200 rounded p-2 text-sm">❌ {error}</div>}

        <div className="grid md:grid-cols-4 gap-3 items-end">
          <div className="md:col-span-2">
            <p className="label">Selected file</p>
            <div className="input bg-slate-50">{selectedFile ? `${selectedFile.name} (${Math.round(selectedFile.size / 1024)} KB)` : 'No file selected'}</div>
          </div>
          <select className="input" value={format} onChange={(e) => setFormat(e.target.value as any)}>
            <option value="auto">Auto</option>
            <option value="parquet">Parquet</option>
            <option value="csv">CSV</option>
          </select>
          <div className="flex gap-2">
            <input ref={fileRef} type="file" accept=".parquet,.csv" className="hidden" onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)} />
            <button className="btn-secondary" onClick={() => fileRef.current?.click()}>Browse...</button>
            <button className="btn" disabled={!selectedFile || loadingUpload} onClick={uploadProfile}>{loadingUpload ? 'Uploading...' : 'Upload + Profile'}</button>
          </div>
        </div>

        <details className="border rounded-lg p-3">
          <summary className="font-medium cursor-pointer">Advanced: Load from server path</summary>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
            <input className="input md:col-span-2" value={path} onChange={(e) => setPath(e.target.value)} placeholder="C:\\data\\glass.parquet" />
            <button className="btn" disabled={!path || loadingPath} onClick={loadFromPath}>{loadingPath ? 'Loading...' : 'Load + Profile'}</button>
          </div>
        </details>
        <p className="text-xs text-slate-500">Current dataset id: {datasetId || 'none'}</p>
      </section>

      {data && (
        <>
          <section className="card space-y-3">
            <p className="font-medium">Rows: {data.rows} | Columns: {data.columns}</p>
            <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
              <div className="border rounded-lg p-3"><p className="font-semibold">Rows</p><p>{data.rows}</p></div>
              <div className="border rounded-lg p-3"><p className="font-semibold">Columns</p><p>{data.columns}</p></div>
              <div className="border rounded-lg p-3"><p className="font-semibold">Targets</p><p>{groups.targets?.length ?? 0}</p></div>
              <div className="border rounded-lg p-3"><p className="font-semibold">Control knobs</p><p>{groups.control_knobs?.length ?? 0}</p></div>
              <div className="border rounded-lg p-3"><p className="font-semibold">Context numeric</p><p>{groups.context_numeric?.length ?? 0}</p></div>
              <div className="border rounded-lg p-3"><p className="font-semibold">Context categorical</p><p>{groups.context_categorical?.length ?? 0}</p></div>
            </div>
          </section>

          <section className="card overflow-auto">
            <h3 className="font-semibold mb-2">Preview (first 20 rows)</h3>
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b bg-slate-50">{previewColumns.map((c) => <th key={c} className="text-left p-2 whitespace-nowrap">{c}</th>)}</tr>
              </thead>
              <tbody>
                {data.preview.map((row, idx) => (
                  <tr key={idx} className="border-b">
                    {previewColumns.map((c) => <td key={c} className="p-2 whitespace-nowrap">{String((row as any)[c] ?? '')}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  )
}
