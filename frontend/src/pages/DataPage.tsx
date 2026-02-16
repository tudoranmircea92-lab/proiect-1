import { useState } from 'react'
import { api } from '../lib/api'

type DebugEntry = { name: string; repr: string }

type LoadResp = {
  rows: number
  columns: number
  preview: Record<string, unknown>[]
  grouped_columns: Record<string, string[]>
  missing_summary: Record<string, number>
  debug?: {
    total_cols?: number
    sample_cols_first_50?: DebugEntry[]
    columns_containing_pwr?: DebugEntry[]
    columns_containing_mainGas?: DebugEntry[]
    columns_containing_s1g?: DebugEntry[]
    warnings?: string[]
  }
}

function InlineWarn({ title, examples }: { title: string; examples: DebugEntry[] }) {
  return (
    <div className="text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 text-xs">
      <p className="font-medium">⚠️ {title}</p>
      <p className="mt-1">Examples: {examples.slice(0, 5).map((x) => x.name).join(', ') || 'none'}</p>
    </div>
  )
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
  const debug = data?.debug ?? {}

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

            <div className="grid md:grid-cols-2 gap-3">
              <div className="border rounded-lg p-3 space-y-1">
                <p className="font-semibold">Power knobs ({groups.power?.length ?? 0})</p>
                <p className="text-xs text-slate-600">{(groups.power ?? []).slice(0, 10).join(', ') || 'None'}</p>
                {(groups.power?.length ?? 0) === 0 && <InlineWarn title="No power knobs matched" examples={debug.columns_containing_pwr ?? []} />}
              </div>
              <div className="border rounded-lg p-3 space-y-1">
                <p className="font-semibold">Main gas knobs ({groups.main_gas?.length ?? 0})</p>
                <p className="text-xs text-slate-600">{(groups.main_gas ?? []).slice(0, 10).join(', ') || 'None'}</p>
                {(groups.main_gas?.length ?? 0) === 0 && <InlineWarn title="No mainGas knobs matched" examples={debug.columns_containing_mainGas ?? []} />}
              </div>
              <div className="border rounded-lg p-3 space-y-1">
                <p className="font-semibold">Segment gas knobs ({groups.segment_gas?.length ?? 0})</p>
                <p className="text-xs text-slate-600">{(groups.segment_gas ?? []).slice(0, 10).join(', ') || 'None'}</p>
                {(groups.segment_gas?.length ?? 0) === 0 && <InlineWarn title="No segment gas knobs matched" examples={debug.columns_containing_s1g ?? []} />}
              </div>
              <div className="border rounded-lg p-3 space-y-1">
                <p className="font-semibold">m*g knobs ({groups.main_gas_alt?.length ?? 0})</p>
                <p className="text-xs text-slate-600">{(groups.main_gas_alt ?? []).slice(0, 10).join(', ') || 'None'}</p>
              </div>
            </div>

            {!!debug.warnings?.length && (
              <div className="border border-amber-300 bg-amber-50 rounded p-2 text-amber-800 text-xs">
                {debug.warnings.map((w, i) => <p key={i}>⚠️ {w}</p>)}
              </div>
            )}

            <div className="border rounded-lg p-3">
              <p className="font-semibold">Keyword-forced context columns ({groups.keyword_forced_context?.length ?? 0})</p>
              <p className="text-xs text-slate-600 mt-1 break-all">{(groups.keyword_forced_context ?? []).join(', ') || 'None'}</p>
            </div>

            <details className="border rounded-lg p-3">
              <summary className="font-semibold cursor-pointer">Debug knob detection</summary>
              <p className="text-xs mt-2">total_cols: {debug.total_cols ?? 0}</p>
              <pre className="text-xs overflow-auto mt-2">{JSON.stringify(debug, null, 2)}</pre>
            </details>
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
