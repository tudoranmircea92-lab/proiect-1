import { useEffect, useMemo, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Alert, Badge, Card, Select } from '../components/ui'
import { stabilityV2 } from '../api/plasma'
import { useDataset } from '../lib/datasetContext'

const RANGES = ['1h', '6h', '24h', '7d'] as const

function statusClass(s: string) {
  if (s === 'Normal') return 'bg-emerald-100 text-emerald-700'
  if (s === 'Medium') return 'bg-amber-100 text-amber-700'
  if (s === 'Critical') return 'bg-red-100 text-red-700'
  return 'bg-slate-100 text-slate-700'
}

export function PlasmaStabilityV2Page() {
  const { datasetId } = useDataset()
  const [range, setRange] = useState<(typeof RANGES)[number]>('24h')
  const [cathode, setCathode] = useState('all')
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const load = async (cath = cathode, preset = range) => {
    if (!datasetId) return
    setLoading(true); setError('')
    try {
      const now = new Date()
      const payload: any = {
        dataset_id: datasetId,
        from: new Date(now.getTime() - 24 * 3600 * 1000).toISOString(),
        to: now.toISOString(),
        aggregation: 'mean',
        active_threshold: 0,
        cathode: cath,
        window_preset: preset,
      }
      const res = await stabilityV2(payload)
      setData(res.data)
    } catch (e: any) {
      setError(e?.message || 'Failed to load plasma stability v2')
    } finally { setLoading(false) }
  }

  useEffect(() => { load('all', '24h') }, [datasetId])

  const cathodes = useMemo(() => ['all', ...Object.keys(data?.series_by_cathode || {})], [data])

  const chartRows = useMemo(() => {
    const by = data?.series_by_cathode || {}
    const keys = Object.keys(by)
    const idx = new Map<string, any>()
    keys.forEach((c: string) => {
      ;(by[c] || []).forEach((p: any) => {
        const t = String(p.ts)
        if (!idx.has(t)) idx.set(t, { ts: t })
        idx.get(t)[c] = p.value
      })
    })
    return [...idx.values()].sort((a, b) => String(a.ts).localeCompare(String(b.ts)))
  }, [data])

  const rows = useMemo(() => [...(data?.scores || [])].sort((a, b) => Number(a.score ?? 1e9) - Number(b.score ?? 1e9)), [data])

  return <div className='space-y-4'>
    {!datasetId && <Alert variant='destructive'>Load dataset first.</Alert>}
    <Card className='space-y-3'>
      <div className='flex flex-wrap gap-2 items-end'>
        <div className='min-w-36'>
          <label className='text-xs text-slate-600'>Range</label>
          <div className='flex rounded-xl border border-blue-200 bg-blue-50 p-1 gap-1'>
            {RANGES.map((r) => <button key={r} className={`px-3 py-1 rounded-lg text-sm ${range === r ? 'bg-white text-blue-700 shadow' : 'text-slate-600'}`} onClick={() => { setRange(r); load(cathode, r) }}>{r}</button>)}
          </div>
        </div>
        <div className='min-w-40'>
          <label className='text-xs text-slate-600'>Cathode</label>
          <Select value={cathode} onChange={(e: any) => { setCathode(e.target.value); load(e.target.value, range) }}>
            {cathodes.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>
        </div>
        {data?.thresholds && <div className='text-xs text-slate-600'>
          thresholds: Normal ≤ {data.thresholds.normal_max}, Medium ≤ {data.thresholds.medium_max}, Critical &gt; {data.thresholds.medium_max}
        </div>}
      </div>
      {error && <Alert variant='destructive'>{error}</Alert>}
      {loading && <p className='text-sm text-slate-500'>Loading…</p>}
    </Card>

    <Card className='h-80'>
      <ResponsiveContainer width='100%' height='100%'>
        <LineChart data={chartRows}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='ts' hide /><YAxis /><Tooltip /><Legend />
          {Object.keys(data?.series_by_cathode || {}).map((c, i) => <Line key={c} type='monotone' dataKey={c} stroke={["#2563eb", "#0ea5e9", "#7c3aed", "#ea580c", "#16a34a"][i % 5]} dot={false} />)}
        </LineChart>
      </ResponsiveContainer>
    </Card>

    <Card>
      <h3 className='text-sm font-medium mb-2'>Cathode ranking</h3>
      {(rows.length === 0) && <p className='text-sm text-slate-500'>No data.</p>}
      {rows.map((r: any) => <div key={r.cathode} className='flex items-center justify-between py-1 border-b last:border-b-0'>
        <div className='flex items-center gap-2'><span className='font-medium'>{r.cathode}</span><Badge className={statusClass(r.status)}>{r.status}</Badge></div>
        <span className='text-sm text-slate-700'>{r.score == null ? '—' : Number(r.score).toFixed(4)}</span>
      </div>)}
    </Card>
  </div>
}
