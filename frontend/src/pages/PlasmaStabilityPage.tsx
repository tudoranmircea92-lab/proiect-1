import { Download, Play } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Alert, Badge, Button, Card, Input, Progress, Select, Skeleton } from '../components/ui'
import { useDataset } from '../lib/datasetContext'
import { runJob } from '../lib/jobs'

type MetricKey = 'score' | 'psi' | 'cv_pwr' | 'cv_current' | 'cv_voltage' | 'gas_cv'

function fmt(v: any, digits = 4) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(digits)
}

function statusBadge(score: number | null | undefined) {
  if (score === null || score === undefined || Number.isNaN(Number(score))) return { text: 'N/A', cls: 'bg-slate-100 text-slate-700' }
  const s = Number(score)
  if (s < 0.01) return { text: 'Excellent', cls: 'bg-emerald-100 text-emerald-700' }
  if (s < 0.02) return { text: 'Good', cls: 'bg-blue-100 text-blue-700' }
  if (s < 0.03) return { text: 'Warning', cls: 'bg-amber-100 text-amber-700' }
  return { text: 'Bad', cls: 'bg-red-100 text-red-700' }
}

export function PlasmaStabilityPage() {
  const { datasetId, globalFilters } = useDataset()
  const now = new Date()
  const [fromTs, setFromTs] = useState(new Date(now.getTime() - 7 * 86400000).toISOString().slice(0, 16))
  const [toTs, setToTs] = useState(now.toISOString().slice(0, 16))
  const [threshold, setThreshold] = useState(0)
  const [agg, setAgg] = useState<'mean' | 'median'>('mean')
  const [result, setResult] = useState<any>(null)
  const [metric, setMetric] = useState<MetricKey>('score')
  const [sortMode, setSortMode] = useState<'cathode' | 'metric_desc'>('metric_desc')
  const [tableSort, setTableSort] = useState<{ key: string; dir: 'asc' | 'desc' }>({ key: 'score', dir: 'desc' })
  const [selectedCathode, setSelectedCathode] = useState<string>('')
  const [showSeries, setShowSeries] = useState({ overall: true, vacuum: true, ucur: true, upwr: true })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')

  const run = async () => {
    if (!datasetId) { setError('Load data first'); return }
    setLoading(true); setError('')
    try {
      const res = await runJob('/api/plasma/stability', {
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
      setResult(res)
    } catch (e: any) {
      setError(e.message || 'Failed to compute plasma stability')
    } finally {
      setLoading(false)
    }
  }

  const trendRows = useMemo(() => {
    if (!result?.trends?.time_bins) return []
    return result.trends.time_bins.map((t: string, i: number) => ({
      bin: t,
      overall_score: result.trends.overall_score?.[i],
      vacuum_cv: result.trends.vacuum_cv?.[i],
      uniformity_cv_current: result.trends.uniformity_cv_current?.[i],
      uniformity_cv_power: result.trends.uniformity_cv_power?.[i],
    }))
  }, [result])

  const barRows = useMemo(() => {
    const rows = [...(result?.per_cathode || [])]
    if (sortMode === 'cathode') rows.sort((a, b) => String(a.cathode).localeCompare(String(b.cathode), undefined, { numeric: true }))
    else rows.sort((a, b) => Number(b?.[metric] ?? -Infinity) - Number(a?.[metric] ?? -Infinity))
    return rows
  }, [result, metric, sortMode])

  const tableRows = useMemo(() => {
    const rows = [...(result?.per_cathode || [])]
    const k = tableSort.key
    const dir = tableSort.dir === 'asc' ? 1 : -1
    rows.sort((a, b) => {
      const av = a?.[k]
      const bv = b?.[k]
      if (typeof av === 'string' || typeof bv === 'string') return dir * String(av ?? '').localeCompare(String(bv ?? ''), undefined, { numeric: true })
      return dir * (Number(av ?? -Infinity) - Number(bv ?? -Infinity))
    })
    return rows
  }, [result, tableSort])

  const selectedBarRows = useMemo(() => {
    if (!selectedCathode) return barRows
    const first = barRows.find((r: any) => r.cathode === selectedCathode)
    const rest = barRows.filter((r: any) => r.cathode !== selectedCathode)
    return first ? [first, ...rest] : barRows
  }, [barRows, selectedCathode])

  const exportCsv = () => {
    if (!result) return
    const header = ['interval_from', 'interval_to', 'rows_used', 'overall_score', 'vacuum_cv', 'uniformity_cv_current', 'uniformity_cv_power', 'avg_active_cathodes', 'cathode', 'active_rate', 'mean_pwr', 'cv_pwr', 'cv_current', 'cv_voltage', 'gas_cv', 'psi', 'score', 'n_active_samples']
    const lines = [header.join(',')]
    ;(result.per_cathode || []).forEach((r: any) => {
      lines.push([
        result.interval?.from,
        result.interval?.to,
        result.interval?.rows_used,
        result.kpis?.overall_score,
        result.kpis?.vacuum_cv,
        result.kpis?.uniformity_cv_current,
        result.kpis?.uniformity_cv_power,
        result.kpis?.avg_active_cathodes,
        r.cathode,
        r.active_rate,
        r.mean_pwr,
        r.cv_pwr,
        r.cv_current,
        r.cv_voltage,
        r.gas_cv,
        r.psi,
        r.score,
        r.n_active_samples,
      ].join(','))
    })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }))
    a.download = 'plasma_stability.csv'
    a.click()
  }

  const state = statusBadge(result?.kpis?.overall_score)

  return <div className='space-y-6'>
    {!datasetId && <Alert variant='destructive'>Load data first.</Alert>}

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Plasma Stability</h3>
      <div className='grid md:grid-cols-5 gap-2 items-end'>
        <div><label className='text-xs text-slate-600'>From</label><Input type='datetime-local' value={fromTs} onChange={(e: any) => setFromTs(e.target.value)} /></div>
        <div><label className='text-xs text-slate-600'>To</label><Input type='datetime-local' value={toTs} onChange={(e: any) => setToTs(e.target.value)} /></div>
        <div><label className='text-xs text-slate-600'>Active threshold</label><Select value={String(threshold)} onChange={(e: any) => setThreshold(Number(e.target.value))}><option value='0'>0.0</option><option value='0.1'>0.1</option><option value='1'>1.0</option></Select></div>
        <div><label className='text-xs text-slate-600'>Aggregation</label><Select value={agg} onChange={(e: any) => setAgg(e.target.value)}><option value='mean'>mean</option><option value='median'>median</option></Select></div>
        <div className='flex gap-2'><Button onClick={run} disabled={!datasetId || loading}><Play size={16} className='inline mr-1' />Run</Button><Button variant='secondary' onClick={exportCsv} disabled={!result}><Download size={16} className='inline mr-1' />Export CSV</Button></div>
      </div>
      {loading && <><Progress value={progress} /><p className='text-sm text-slate-500'>{stage}</p></>}
      {error && <Alert variant='destructive'>{error}</Alert>}
    </Card>

    {!result && !loading && <Alert>Run stability analysis to see results.</Alert>}
    {loading && <div className='grid md:grid-cols-5 gap-3'>{[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className='h-20' />)}</div>}

    {result && <>
      <div className='grid md:grid-cols-5 gap-3'>
        <Card><p className='text-xs text-slate-500'>Overall Stability Score</p><p className='text-2xl font-semibold'>{fmt(result.kpis?.overall_score)}</p><Badge className={state.cls}>{state.text}</Badge></Card>
        <Card><p className='text-xs text-slate-500'>Vacuum CV</p><p className='text-2xl font-semibold'>{fmt(result.kpis?.vacuum_cv)}</p></Card>
        <Card><p className='text-xs text-slate-500'>Uniformity CV Current</p><p className='text-2xl font-semibold'>{fmt(result.kpis?.uniformity_cv_current)}</p></Card>
        <Card><p className='text-xs text-slate-500'>Uniformity CV Power</p><p className='text-2xl font-semibold'>{fmt(result.kpis?.uniformity_cv_power)}</p></Card>
        <Card><p className='text-xs text-slate-500'>Avg active cathodes</p><p className='text-2xl font-semibold'>{fmt(result.kpis?.avg_active_cathodes, 2)}</p></Card>
      </div>

      <Card className='space-y-2'>
        <div className='flex flex-wrap gap-2 items-center justify-between'>
          <h3 className='text-sm font-medium tracking-tight'>Trend</h3>
          <div className='flex gap-2 text-xs'>
            <Button variant={showSeries.overall ? 'default' : 'secondary'} onClick={() => setShowSeries({ ...showSeries, overall: !showSeries.overall })}>overall</Button>
            <Button variant={showSeries.vacuum ? 'default' : 'secondary'} onClick={() => setShowSeries({ ...showSeries, vacuum: !showSeries.vacuum })}>vacuum</Button>
            <Button variant={showSeries.ucur ? 'default' : 'secondary'} onClick={() => setShowSeries({ ...showSeries, ucur: !showSeries.ucur })}>uniform cur</Button>
            <Button variant={showSeries.upwr ? 'default' : 'secondary'} onClick={() => setShowSeries({ ...showSeries, upwr: !showSeries.upwr })}>uniform pwr</Button>
          </div>
        </div>
        <Card className='h-80'>
          <ResponsiveContainer width='100%' height='100%'>
            <LineChart data={trendRows}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='bin' hide /><YAxis /><Tooltip /><Legend />
              {showSeries.overall && <Line type='monotone' dataKey='overall_score' stroke='#2563eb' dot={false} />}
              {showSeries.vacuum && <Line type='monotone' dataKey='vacuum_cv' stroke='#0f766e' dot={false} />}
              {showSeries.ucur && <Line type='monotone' dataKey='uniformity_cv_current' stroke='#9333ea' dot={false} />}
              {showSeries.upwr && <Line type='monotone' dataKey='uniformity_cv_power' stroke='#b45309' dot={false} />}
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </Card>

      <Card className='space-y-2'>
        <div className='flex flex-wrap gap-2 items-end'>
          <div><label className='text-xs text-slate-600'>Bar metric</label><Select value={metric} onChange={(e: any) => setMetric(e.target.value)}><option value='score'>score</option><option value='psi'>psi</option><option value='cv_pwr'>cv_pwr</option><option value='cv_current'>cv_current</option><option value='cv_voltage'>cv_voltage</option><option value='gas_cv'>gas_cv</option></Select></div>
          <div><label className='text-xs text-slate-600'>Sort</label><Select value={sortMode} onChange={(e: any) => setSortMode(e.target.value)}><option value='metric_desc'>metric desc</option><option value='cathode'>cathode id</option></Select></div>
        </div>
        <Card className='h-80'>
          <ResponsiveContainer width='100%' height='100%'>
            <BarChart data={selectedBarRows}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='cathode' /><YAxis /><Tooltip /><Bar dataKey={metric} fill='#2563eb' onClick={(data: any) => setSelectedCathode(data?.cathode || '')} /></BarChart>
          </ResponsiveContainer>
        </Card>
      </Card>

      <Card className='space-y-2'>
        <h3 className='text-sm font-medium tracking-tight'>Per-cathode details</h3>
        <div className='overflow-auto'>
          <table className='min-w-full text-sm'>
            <thead>
              <tr className='border-b'>
                {['cathode', 'active_rate', 'mean_pwr', 'cv_pwr', 'cv_current', 'cv_voltage', 'gas_cv', 'psi', 'score', 'n_active_samples'].map((k) => (
                  <th key={k} className='text-left p-2 cursor-pointer' onClick={() => setTableSort({ key: k, dir: tableSort.key === k && tableSort.dir === 'asc' ? 'desc' : 'asc' })}>{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.map((r: any) => (
                <tr key={r.cathode} className={`border-b ${selectedCathode === r.cathode ? 'bg-blue-50' : ''}`} onClick={() => setSelectedCathode(r.cathode)}>
                  <td className='p-2'>{r.cathode}</td>
                  <td className='p-2'>{fmt(r.active_rate)}</td>
                  <td className='p-2'>{fmt(r.mean_pwr)}</td>
                  <td className='p-2'>{fmt(r.cv_pwr)}</td>
                  <td className='p-2'>{fmt(r.cv_current)}</td>
                  <td className='p-2'>{fmt(r.cv_voltage)}</td>
                  <td className='p-2'>{fmt(r.gas_cv)}</td>
                  <td className='p-2'>{fmt(r.psi)}</td>
                  <td className='p-2'>{fmt(r.score)}</td>
                  <td className='p-2'>{r.n_active_samples ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>}
  </div>
}
