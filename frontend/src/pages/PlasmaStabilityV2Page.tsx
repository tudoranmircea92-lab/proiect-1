import { useEffect, useMemo, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Alert, Badge, Button, Card, Input, Select } from '../components/ui'
import { columns, stabilityV2 } from '../api/plasma'
import { useDataset } from '../lib/datasetContext'

const RANGES = ['1h', '6h', '24h', '7d'] as const

function computeFromTo(toIso: string, preset: (typeof RANGES)[number]) {
  const hrs = { '1h': 1, '6h': 6, '24h': 24, '7d': 24 * 7 }[preset]
  const to = new Date(toIso)
  const from = new Date(to.getTime() - hrs * 3600 * 1000)
  return { from: from.toISOString(), to: to.toISOString() }
}

function statusClass(s: string) {
  if (s === 'Normal') return 'bg-emerald-100 text-emerald-700'
  if (s === 'Medium') return 'bg-amber-100 text-amber-700'
  if (s === 'Critical') return 'bg-red-100 text-red-700'
  return 'bg-slate-100 text-slate-700'
}

export function PlasmaStabilityV2Page() {
  const { datasetId, products, thicknesses } = useDataset()
  const [range, setRange] = useState<(typeof RANGES)[number]>('24h')
  const [cathode, setCathode] = useState('all')
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [toTs, setToTs] = useState<string | null>(null)
  const [fromTs, setFromTs] = useState<string | null>(null)
  const [selectedProducts, setSelectedProducts] = useState<string[]>([])
  const [selectedThicknesses, setSelectedThicknesses] = useState<number[]>([])

  const toggleProduct = (val: string) => {
    setSelectedProducts((prev) => prev.includes(val) ? prev.filter((x) => x !== val) : [...prev, val])
  }

  const toggleThickness = (val: string) => {
    const num = Number(val)
    if (!Number.isFinite(num)) return
    setSelectedThicknesses((prev) => prev.includes(num) ? prev.filter((x) => x !== num) : [...prev, num])
  }

  const toLocalInputValue = (iso: string | null) => {
    if (!iso) return ''
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
  }

  const fromInputToIso = (local: string) => {
    const d = new Date(local)
    if (Number.isNaN(d.getTime())) return null
    return d.toISOString()
  }

  const load = async (
    cath = cathode,
    preset = range,
    anchorTo: string | null = toTs,
    explicitWindow?: { from: string; to: string },
  ) => {
    if (!datasetId) return
    setLoading(true); setError('')
    try {
      let effectiveTo = anchorTo
      if (!effectiveTo) {
        const meta = await columns()
        effectiveTo = meta?.data?.defaults?.latest_ts || new Date().toISOString()
      }
      const w = explicitWindow || computeFromTo(String(effectiveTo), preset)
      setToTs(w.to); setFromTs(w.from)
      const payload: any = {
        dataset_id: datasetId,
        from: w.from,
        to: w.to,
        aggregation: 'mean',
        active_threshold: 0,
        cathode: cath,
        window_preset: explicitWindow ? undefined : preset,
        filters: {
          product: selectedProducts,
          thickness_mm: selectedThicknesses,
        },
      }
      const res = await stabilityV2(payload)
      setData(res.data)
    } catch (e: any) {
      setError(e?.message || 'Failed to load plasma stability v2')
    } finally { setLoading(false) }
  }

  useEffect(() => {
    if (!datasetId) return
    ;(async () => {
      try {
        const meta = await columns()
        const latest = meta?.data?.defaults?.latest_ts || new Date().toISOString()
        const w = computeFromTo(latest, '24h')
        setRange('24h'); setCathode('all'); setToTs(w.to); setFromTs(w.from)
        await load('all', '24h', latest)
      } catch {
        await load('all', '24h', new Date().toISOString())
      }
    })()
  }, [datasetId])

  const applyCustomRange = async () => {
    const fromIso = fromTs
    const toIso = toTs
    if (!fromIso || !toIso) {
      setError('Please provide a valid From/To date-time range')
      return
    }
    if (new Date(fromIso) >= new Date(toIso)) {
      setError('From must be earlier than To')
      return
    }
    await load(cathode, range, toIso, { from: fromIso, to: toIso })
  }

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
            {RANGES.map((r) => <button key={r} className={`px-3 py-1 rounded-lg text-sm ${range === r ? 'bg-white text-blue-700 shadow' : 'text-slate-600'}`} onClick={() => { setRange(r); load(cathode, r, toTs) }}>{r}</button>)}
          </div>
        </div>
        <div className='min-w-40'>
          <label className='text-xs text-slate-600'>Cathode</label>
          <Select value={cathode} onChange={(e: any) => { setCathode(e.target.value); load(e.target.value, range, toTs) }}>
            {cathodes.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>
        </div>
        <div className='min-w-44'>
          <label className='text-xs text-slate-600'>Product filter</label>
          <Select value='' onChange={(e: any) => { if (e.target.value) toggleProduct(e.target.value) }}>
            <option value=''>All products</option>
            {products.map((p) => <option key={p} value={p}>{p}</option>)}
          </Select>
          {selectedProducts.length > 0 && <p className='text-[11px] text-blue-700 mt-1'>{selectedProducts.join(', ')}</p>}
          <Button className='mt-1' variant='ghost' onClick={() => { setSelectedProducts([]); load(cathode, range, toTs) }}>Clear</Button>
        </div>
        <div className='min-w-44'>
          <label className='text-xs text-slate-600'>Thickness filter</label>
          <Select value='' onChange={(e: any) => { if (e.target.value) toggleThickness(e.target.value) }}>
            <option value=''>All thicknesses</option>
            {thicknesses.map((t) => <option key={String(t)} value={String(t)}>{String(t)}</option>)}
          </Select>
          {selectedThicknesses.length > 0 && <p className='text-[11px] text-blue-700 mt-1'>{selectedThicknesses.join(', ')}</p>}
          <Button className='mt-1' variant='ghost' onClick={() => { setSelectedThicknesses([]); load(cathode, range, toTs) }}>Clear</Button>
        </div>
      </div>
      <div className='flex flex-wrap gap-2 items-end'>
        <div>
          <label className='text-xs text-slate-600'>From</label>
          <Input type='datetime-local' value={toLocalInputValue(fromTs)} onChange={(e: any) => setFromTs(fromInputToIso(e.target.value))} />
        </div>
        <div>
          <label className='text-xs text-slate-600'>To</label>
          <Input type='datetime-local' value={toLocalInputValue(toTs)} onChange={(e: any) => setToTs(fromInputToIso(e.target.value))} />
        </div>
        <Button variant='secondary' onClick={applyCustomRange}>Apply time range</Button>
        <Button variant='secondary' onClick={() => load(cathode, range, toTs)}>Apply product/thickness</Button>
        {data?.thresholds && <div className='text-xs text-slate-600'>
          thresholds: Normal ≤ {data.thresholds.normal_max}, Medium ≤ {data.thresholds.medium_max}, Critical &gt; {data.thresholds.medium_max}
        </div>}
      </div>
      {(fromTs && toTs) && <p className='text-xs text-slate-500'>Effective window: {fromTs} → {toTs}</p>}
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
