import { Download, Play } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Accordion, Alert, Badge, Button, Card, Input, Progress, Select, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'
import { runJobWithMeta } from '../lib/jobs'

function fmt(v: any, d = 4) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d)
}

function level(score: number | null | undefined) {
  if (score === null || score === undefined || Number.isNaN(Number(score))) return { label: 'N/A', cls: 'bg-slate-100 text-slate-700' }
  const s = Number(score)
  if (s < 0.01) return { label: 'Excellent', cls: 'bg-emerald-100 text-emerald-700' }
  if (s < 0.02) return { label: 'Good', cls: 'bg-blue-100 text-blue-700' }
  if (s < 0.03) return { label: 'Warning', cls: 'bg-amber-100 text-amber-700' }
  return { label: 'Bad', cls: 'bg-red-100 text-red-700' }
}

export function PlasmaStabilityPage() {
  const { datasetId, globalFilters } = useDataset()
  const now = new Date()
  const [fromTs, setFromTs] = useState(new Date(now.getTime() - 7 * 86400000).toISOString().slice(0, 16))
  const [toTs, setToTs] = useState(now.toISOString().slice(0, 16))
  const [threshold, setThreshold] = useState(0)
  const [agg, setAgg] = useState<'mean' | 'median'>('mean')
  const [result, setResult] = useState<any>(null)
  const [jobId, setJobId] = useState('')
  const [metric, setMetric] = useState<'score' | 'psi' | 'cv_pwr' | 'cv_current' | 'cv_voltage' | 'gas_cv'>('score')
  const [sort, setSort] = useState<'cathode' | 'metric_desc'>('metric_desc')
  const [selectedCathode, setSelectedCathode] = useState('')
  const [errorObj, setErrorObj] = useState<any>(null)
  const [plasmaReady, setPlasmaReady] = useState(true)
  const [healthMsg, setHealthMsg] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')


  useEffect(() => {
    let mounted = true
    api.get('/api/plasma/health').then(() => {
      if (!mounted) return
      setPlasmaReady(true)
      setHealthMsg('')
    }).catch((e: any) => {
      if (!mounted) return
      setPlasmaReady(false)
      const status = e?.response?.status
      const detail = e?.response?.data?.detail
      setHealthMsg(`Plasma backend not available. Check that /api/plasma is mounted. Open /docs and confirm plasma endpoints exist. ${status ? `(status ${status})` : ''} ${detail ? `- ${JSON.stringify(detail)}` : ''}`)
    })
    return () => { mounted = false }
  }, [datasetId])

  const run = async () => {
    if (!datasetId) {
      setErrorObj({ detail: 'Dataset not loaded', hint: 'Load data first in Data tab', action: 'Go to Data → Load + Profile' })
      return
    }
    setLoading(true)
    setErrorObj(null)
    try {
      const { jobId, result } = await runJobWithMeta('/api/plasma/stability', {
        dataset_id: datasetId,
        timestamp_col: 'auto',
        from: fromTs,
        to: toTs,
        active_threshold: threshold,
        agg,
        weights: { vacuum: 0.7, uniform_cur: 0.7, uniform_pwr: 0.7 },
        bins: 'auto',
        filter: {
          products: globalFilters.products,
          thicknesses: globalFilters.thicknesses,
          date_from: globalFilters.dateFrom || null,
          date_to: globalFilters.dateTo || null,
        },
      }, ({ progress, stage }) => { setProgress(progress); setStage(stage) })
      setJobId(jobId)
      setResult(result)
    } catch (e: any) {
      const status = e?.response?.status ?? null
      const url = `${e?.config?.baseURL || ''}${e?.config?.url || '/api/plasma/stability'}`
      const response = e?.response?.data ?? null
      const detail = (typeof response?.detail === 'string' ? response.detail : e?.message) || 'Unknown error'
      setErrorObj({
        detail,
        hint: response?.hint,
        action: response?.action,
        status,
        url,
        response,
      })
    } finally {
      setLoading(false)
    }
  }

  const trendRows = useMemo(() => {
    if (!result?.trends?.time_bins) return []
    return result.trends.time_bins.map((t: string, i: number) => ({
      time: t,
      overall_score: result.trends.overall_score?.[i],
      vacuum_cv: result.trends.vacuum_cv?.[i],
      uniformity_cv_current: result.trends.uniformity_cv_current?.[i],
      uniformity_cv_power: result.trends.uniformity_cv_power?.[i],
    }))
  }, [result])

  const cathodeRows = useMemo(() => {
    const rows = [...(result?.per_cathode || [])]
    if (sort === 'cathode') rows.sort((a, b) => String(a.cathode).localeCompare(String(b.cathode), undefined, { numeric: true }))
    else rows.sort((a, b) => Number(b?.[metric] ?? -Infinity) - Number(a?.[metric] ?? -Infinity))
    return rows
  }, [result, sort, metric])

  const state = level(result?.kpis?.overall_score)

  const exportCsv = async () => {
    try {
      const url = jobId ? `/api/plasma/export_csv?job_id=${jobId}` : '/api/plasma/export_csv'
      const r = await api.get(url, { responseType: 'blob' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(new Blob([r.data], { type: 'text/csv' }))
      a.download = 'plasma_stability.csv'
      a.click()
    } catch (e: any) {
      setErrorObj({
        detail: 'Export failed',
        status: e?.response?.status ?? null,
        url: `${e?.config?.baseURL || ''}${e?.config?.url || '/api/plasma/export_csv'}`,
        response: e?.response?.data ?? e?.message,
      })
    }
  }

  return <div className='space-y-6'>
    {!datasetId && <Alert variant='destructive'>Load data first.</Alert>}

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Plasma Stability</h3>
      <div className='grid md:grid-cols-5 gap-2 items-end'>
        <div><label className='text-xs text-slate-600'>From</label><Input type='datetime-local' value={fromTs} onChange={(e: any) => setFromTs(e.target.value)} /></div>
        <div><label className='text-xs text-slate-600'>To</label><Input type='datetime-local' value={toTs} onChange={(e: any) => setToTs(e.target.value)} /></div>
        <div><label className='text-xs text-slate-600'>Active threshold</label><Select value={String(threshold)} onChange={(e: any) => setThreshold(Number(e.target.value))}><option value='0'>0.0</option><option value='0.1'>0.1</option><option value='1'>1.0</option></Select></div>
        <div><label className='text-xs text-slate-600'>Aggregation</label><Select value={agg} onChange={(e: any) => setAgg(e.target.value)}><option value='mean'>mean</option><option value='median'>median</option></Select></div>
        <div className='flex gap-2'><Button onClick={run} disabled={!datasetId || loading || !plasmaReady}><Play size={16} className='inline mr-1' />Run</Button><Button variant='secondary' onClick={exportCsv} disabled={!result}><Download size={16} className='inline mr-1' />Export CSV</Button></div>
      </div>

      {!plasmaReady && <Alert variant='destructive'>{healthMsg}</Alert>}

      <Accordion title='How this score is computed'>
        <div className='grid md:grid-cols-2 gap-3 text-sm'>
          <div>
            <p className='mb-2'>We quantify stability by measuring how much key signals fluctuate relative to their average. Lower score = more stable plasma.</p>
            <ul className='list-disc pl-5 space-y-1'>
              <li>CV = std / mean</li>
              <li>PSI = 0.5×CV(power) + 0.3×CV(current) + 0.2×CV(voltage)</li>
              <li>Gas stability = mean CV over available segment gases (s1..s11)</li>
              <li>Cathode score = 0.6×PSI + 0.4×GasStability (if gas missing → score = PSI)</li>
              <li>Overall score = median(active cathode scores) + vacuum/uniformity penalties</li>
            </ul>
          </div>
          <div className='space-y-2'>
            <p><b>Active cathode rule:</b> power &gt; active_threshold.</p>
            <div className='flex flex-wrap gap-2'>
              <Badge className='bg-emerald-100 text-emerald-700'>Excellent: &lt; 0.01</Badge>
              <Badge className='bg-blue-100 text-blue-700'>Good: 0.01–0.02</Badge>
              <Badge className='bg-amber-100 text-amber-700'>Warning: 0.02–0.03</Badge>
              <Badge className='bg-red-100 text-red-700'>Bad: &gt; 0.03</Badge>
            </div>
          </div>
        </div>
      </Accordion>

      {loading && <><Progress value={progress} /><p className='text-sm text-slate-500'>{stage}</p></>}

      {errorObj && <Alert variant='destructive'>
        <p className='font-medium'>Plasma stability failed</p>
        <p>{errorObj.detail || 'Unknown error'}</p>
        {errorObj.hint && <p className='text-xs mt-1'>Hint: {errorObj.hint}</p>}
        {errorObj.action && <Button className='mt-2' variant='secondary'>{errorObj.action}</Button>}
        <Accordion title='Show details'>
          <div className='text-xs space-y-1'>
            <p>Status: {errorObj.status ?? '—'}</p>
            <p>URL: {errorObj.url ?? '—'}</p>
            <pre className='overflow-auto'>{JSON.stringify(errorObj.response ?? errorObj, null, 2)}</pre>
          </div>
        </Accordion>
      </Alert>}
    </Card>

    {!result && !loading && <Alert>Run stability analysis to see results.</Alert>}
    {loading && <div className='grid md:grid-cols-5 gap-3'>{[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className='h-20' />)}</div>}

    {result && <>
      <div className='grid md:grid-cols-5 gap-3'>
        <Card><p className='text-xs text-slate-500'>Overall score</p><p className='text-2xl font-semibold'>{fmt(result.kpis?.overall_score)}</p><Badge className={state.cls}>{state.label}</Badge></Card>
        <Card><p className='text-xs text-slate-500'>Vacuum CV</p><p className='text-2xl font-semibold'>{fmt(result.kpis?.vacuum_cv)}</p></Card>
        <Card><p className='text-xs text-slate-500'>Uniformity CV current</p><p className='text-2xl font-semibold'>{fmt(result.kpis?.uniformity_cv_current)}</p></Card>
        <Card><p className='text-xs text-slate-500'>Uniformity CV power</p><p className='text-2xl font-semibold'>{fmt(result.kpis?.uniformity_cv_power)}</p></Card>
        <Card><p className='text-xs text-slate-500'>Avg active cathodes</p><p className='text-2xl font-semibold'>{fmt(result.kpis?.avg_active_cathodes, 2)}</p></Card>
      </div>

      <Card className='space-y-2'>
        <h3 className='text-sm font-medium tracking-tight'>Data notes</h3>
        <div className='grid md:grid-cols-2 gap-2 text-sm'>
          <div>Rows used: {result.data_notes?.rows_used ?? result.interval?.rows_used ?? '—'}</div>
          <div>Active cathodes avg: {fmt(result.data_notes?.avg_active_cathodes ?? result.kpis?.avg_active_cathodes, 2)}</div>
          <div>Gas segments missing (ignored): {result.data_notes?.gas_segments_missing ?? '—'}</div>
          <div>Computation: {result.data_notes?.computation_mode ?? 'across plates (wide dataset)'}</div>
        </div>
      </Card>

      <Card className='h-80'>
        <h3 className='text-sm font-medium mb-2'>Trend over time bins (overall score)</h3>
        <ResponsiveContainer width='100%' height='90%'>
          <LineChart data={trendRows}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='time' hide /><YAxis /><Tooltip /><Line type='monotone' dataKey='overall_score' stroke='#2563eb' dot={false} /></LineChart>
        </ResponsiveContainer>
      </Card>

      <Card className='space-y-2'>
        <div className='flex gap-2 items-end'>
          <div><label className='text-xs text-slate-600'>Metric</label><Select value={metric} onChange={(e: any) => setMetric(e.target.value)}><option value='score'>score</option><option value='psi'>psi</option><option value='cv_pwr'>cv_pwr</option><option value='cv_current'>cv_cur</option><option value='cv_voltage'>cv_volt</option><option value='gas_cv'>gas_cv</option></Select></div>
          <div><label className='text-xs text-slate-600'>Sort</label><Select value={sort} onChange={(e: any) => setSort(e.target.value)}><option value='metric_desc'>metric desc</option><option value='cathode'>cathode id</option></Select></div>
        </div>
        <Card className='h-80'>
          <ResponsiveContainer width='100%' height='100%'>
            <BarChart data={cathodeRows}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='cathode' /><YAxis /><Tooltip /><Bar dataKey={metric} fill='#2563eb' onClick={(d: any) => setSelectedCathode(d?.cathode || '')} /></BarChart>
          </ResponsiveContainer>
        </Card>
      </Card>

      <Card className='overflow-auto'>
        <h3 className='text-sm font-medium mb-2'>Per-cathode metrics</h3>
        <table className='min-w-full text-sm'>
          <thead><tr className='border-b'><th className='p-2 text-left'>cathode</th><th className='p-2 text-left'>active_rate</th><th className='p-2 text-left'>psi</th><th className='p-2 text-left'>gas_cv</th><th className='p-2 text-left'>score</th><th className='p-2 text-left'>cv_pwr</th><th className='p-2 text-left'>cv_cur</th><th className='p-2 text-left'>cv_volt</th><th className='p-2 text-left'>n_active_samples</th></tr></thead>
          <tbody>
            {cathodeRows.map((r: any) => <tr key={r.cathode} className={`border-b ${selectedCathode === r.cathode ? 'bg-blue-50' : ''}`}><td className='p-2'>{r.cathode}</td><td className='p-2'>{fmt(r.active_rate)}</td><td className='p-2'>{fmt(r.psi)}</td><td className='p-2'>{fmt(r.gas_cv)}</td><td className='p-2'>{fmt(r.score)}</td><td className='p-2'>{fmt(r.cv_pwr)}</td><td className='p-2'>{fmt(r.cv_current)}</td><td className='p-2'>{fmt(r.cv_voltage)}</td><td className='p-2'>{r.n_active_samples ?? '—'}</td></tr>)}
          </tbody>
        </table>
      </Card>
    </>}
  </div>
}
