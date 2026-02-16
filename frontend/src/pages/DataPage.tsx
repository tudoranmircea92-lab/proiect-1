import { useState } from 'react'
import { api } from '../lib/api'

type LoadResp = {
  rows: number
  columns: number
  preview: Record<string, unknown>[]
  grouped_columns: Record<string, string[]>
  missing_summary: Record<string, number>
}

export function DataPage() {
  const [path, setPath] = useState('')
  const [format, setFormat] = useState<'auto' | 'csv' | 'parquet'>('auto')
  const [data, setData] = useState<LoadResp | null>(null)
  const [error, setError] = useState('')

  const load = async () => {
    setError('')
    try {
      const res = await api.post('/api/data/load', { path, format })
      setData(res.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Failed to load data')
    }
  }

  const groups = data?.grouped_columns ?? {}

  return (
    <div className="space-y-4">
      <section className="card space-y-3">
        <h2 className="text-lg font-semibold">Data</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input className="input md:col-span-2" value={path} onChange={(e) => setPath(e.target.value)} placeholder="/path/to/dataset.parquet" />
          <select className="input" value={format} onChange={(e) => setFormat(e.target.value as any)}>
            <option value="auto">Auto</option>
            <option value="parquet">Parquet</option>
            <option value="csv">CSV</option>
          </select>
        </div>
        <button className="btn" onClick={load}>Load + Profile</button>
        {error && <p className="text-red-600 text-sm">{error}</p>}
      </section>

      {data && (
        <>
          <section className="card space-y-3">
            <p className="font-medium">Rows: {data.rows} | Columns: {data.columns}</p>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="border rounded-lg p-3"><p className="font-semibold">Targets</p><p>{groups.targets?.length ?? 0}</p></div>
              <div className="border rounded-lg p-3"><p className="font-semibold">Control knobs</p><p>{groups.control_knobs?.length ?? 0}</p></div>
              <div className="border rounded-lg p-3"><p className="font-semibold">Context numeric</p><p>{groups.context_numeric?.length ?? 0}</p></div>
              <div className="border rounded-lg p-3"><p className="font-semibold">Context categorical</p><p>{groups.context_categorical?.length ?? 0}</p></div>
            </div>
            <div className="border rounded-lg p-3">
              <p className="font-semibold">Keyword-forced context columns ({groups.keyword_forced_context?.length ?? 0})</p>
              <p className="text-xs text-slate-600 mt-1 break-all">{(groups.keyword_forced_context ?? []).join(', ') || 'None'}</p>
            </div>
          </section>
          <section className="card overflow-auto">
            <h3 className="font-semibold mb-2">Preview (first 20 rows)</h3>
            <pre className="text-xs">{JSON.stringify(data.preview, null, 2)}</pre>
          </section>
        </>
      )}
    </div>
  )
}
