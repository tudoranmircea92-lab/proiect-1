import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../lib/api'

const metricOptions = ['cv_current','cv_power','ripple_current','ripple_power','vacuum_cv','uniformity_cv_current','uniformity_cv_power']

export function PlasmaStabilityPage() {
  const [path, setPath] = useState('')
  const [mode, setMode] = useState<'auto'|'timeseries'|'wide_auto'>('auto')
  const [dateFrom, setDateFrom] = useState('2024-01-01')
  const [dateTo, setDateTo] = useState('2024-12-31')
  const [timeFrom, setTimeFrom] = useState('')
  const [timeTo, setTimeTo] = useState('')
  const [activeThreshold, setActiveThreshold] = useState(0)
  const [metrics, setMetrics] = useState<string[]>(['cv_power'])
  const [agg, setAgg] = useState<'mean'|'median'>('mean')
  const [rollingWindowSec, setRollingWindowSec] = useState(30)
  const [showInactive, setShowInactive] = useState(false)
  const [weights, setWeights] = useState({ cv_power:1, cv_current:1, ripple_power:0.5, ripple_current:0.5, vacuum_cv:0.5, uniformity_cv_power:0.7, uniformity_cv_current:0.7 })
  const [sortBy, setSortBy] = useState<'cathode'|'metric'>('metric')
  const [metricForChart, setMetricForChart] = useState('cv_power')
  const [selectedCathodes, setSelectedCathodes] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<any>(null)

  const run = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/api/plasma_stability', {
        path_or_dataset_id: path || null,
        mode,
        date_from: dateFrom,
        date_to: dateTo,
        time_from: timeFrom || null,
        time_to: timeTo || null,
        active_threshold: activeThreshold,
        metrics,
        rolling_window_sec: rollingWindowSec,
        agg,
        weights,
        show_inactive: showInactive,
      })
      setResult(res.data)
      const initial = (res.data.per_cathode || []).slice(0, 3).map((x:any) => x.cathode_id)
      setSelectedCathodes(initial)
    } catch (e:any) {
      setError(e?.response?.data?.detail ?? 'Failed to compute plasma stability')
    } finally {
      setLoading(false)
    }
  }

  const perCathodeSorted = useMemo(() => {
    if (!result?.per_cathode) return []
    const arr = [...result.per_cathode]
    if (sortBy === 'cathode') return arr.sort((a,b)=>String(a.cathode_id).localeCompare(String(b.cathode_id), undefined, { numeric: true }))
    return arr.sort((a,b)=>(b[metricForChart] ?? 0) - (a[metricForChart] ?? 0))
  }, [result, sortBy, metricForChart])

  const trendData = useMemo(() => {
    if (!result?.timeseries) return []
    const merged: Record<string, any> = {}
    for (const c of selectedCathodes) {
      const series = result.timeseries[c] || []
      for (const p of series) {
        const key = p.ts
        if (!merged[key]) merged[key] = { ts: key }
        merged[key][`${c}_${metricForChart}`] = p[metricForChart]
      }
    }
    return Object.values(merged).sort((a:any,b:any)=>String(a.ts).localeCompare(String(b.ts)))
  }, [result, selectedCathodes, metricForChart])

  const exportData = (fmt: 'csv'|'json') => {
    window.open(`http://localhost:8000/api/plasma_stability/export?format=${fmt}`, '_blank')
  }

  const quantileColor = (v: number, values: number[]) => {
    if (!values.length) return '#f8fafc'
    const sorted = [...values].sort((a,b)=>a-b)
    const q1 = sorted[Math.floor(sorted.length*0.25)] ?? 0
    const q2 = sorted[Math.floor(sorted.length*0.5)] ?? 0
    const q3 = sorted[Math.floor(sorted.length*0.75)] ?? 0
    if (v <= q1) return '#e0f2fe'
    if (v <= q2) return '#bae6fd'
    if (v <= q3) return '#7dd3fc'
    return '#38bdf8'
  }

  return <div className='space-y-4'>
    <section className='card space-y-3'>
      <h2 className='text-lg font-semibold'>Plasma Stability</h2>
      <div className='grid md:grid-cols-5 gap-2'>
        <input className='input md:col-span-2' value={path} onChange={e=>setPath(e.target.value)} placeholder='Dataset path (optional, uses loaded dataset if empty)' />
        <select className='input' value={mode} onChange={e=>setMode(e.target.value as any)}><option value='auto'>Auto</option><option value='timeseries'>Force timeseries</option><option value='wide_auto'>Force wide</option></select>
        <select className='input' value={String(activeThreshold)} onChange={e=>setActiveThreshold(Number(e.target.value))}><option value='0'>0</option><option value='0.1'>0.1</option><option value='1'>1.0</option></select>
        <select className='input' value={agg} onChange={e=>setAgg(e.target.value as any)}><option value='mean'>mean</option><option value='median'>median</option></select>
      </div>
      <div className='grid md:grid-cols-6 gap-2'>
        <input className='input' type='date' value={dateFrom} onChange={e=>setDateFrom(e.target.value)} />
        <input className='input' type='date' value={dateTo} onChange={e=>setDateTo(e.target.value)} />
        <input className='input' type='time' value={timeFrom} onChange={e=>setTimeFrom(e.target.value)} />
        <input className='input' type='time' value={timeTo} onChange={e=>setTimeTo(e.target.value)} />
        <input className='input' type='number' value={rollingWindowSec} onChange={e=>setRollingWindowSec(Number(e.target.value))} placeholder='Rolling sec' />
        <label className='flex items-center gap-2 text-sm'><input type='checkbox' checked={showInactive} onChange={e=>setShowInactive(e.target.checked)}/>Show inactive</label>
      </div>
      <div className='grid md:grid-cols-7 gap-2'>
        {metricOptions.map(m=><label key={m} className='text-xs flex items-center gap-2'><input type='checkbox' checked={metrics.includes(m)} onChange={e=>setMetrics(e.target.checked ? [...metrics, m] : metrics.filter(x=>x!==m))}/>{m}</label>)}
      </div>
      <div className='grid md:grid-cols-7 gap-2'>
        {Object.entries(weights).map(([k,v])=><label key={k} className='text-xs'>{k}<input className='input' type='number' step='0.1' value={v} onChange={e=>setWeights({...weights,[k]:Number(e.target.value)})}/></label>)}
      </div>
      <button className='btn' onClick={run} disabled={loading}>{loading ? 'Running...' : 'Run Plasma Stability'}</button>
      {error && <p className='text-red-600 text-sm'>{error}</p>}
    </section>

    {result && <>
      <section className='grid md:grid-cols-5 gap-3'>
        <div className='card'><p className='label'>Overall Stability Score</p><p className='text-xl font-semibold'>{(result.summary.overall_stability_score ?? 0).toFixed(4)}</p></div>
        <div className='card'><p className='label'>Vacuum CV</p><p className='text-xl font-semibold'>{(result.summary.vacuum_cv ?? 0).toFixed(4)}</p></div>
        <div className='card'><p className='label'>Uniformity CV Current</p><p className='text-xl font-semibold'>{(result.summary.uniformity_cv_current ?? 0).toFixed(4)}</p></div>
        <div className='card'><p className='label'>Uniformity CV Power</p><p className='text-xl font-semibold'>{(result.summary.uniformity_cv_power ?? 0).toFixed(4)}</p></div>
        <div className='card'><p className='label'>Active Cathodes</p><p className='text-xl font-semibold'>{Math.round(result.summary.active_cathodes_count ?? 0)}</p></div>
      </section>

      <section className='card space-y-2'>
        <div className='flex gap-2'>
          <select className='input max-w-xs' value={metricForChart} onChange={e=>setMetricForChart(e.target.value)}>{metricOptions.map(m=><option key={m} value={m}>{m}</option>)}</select>
          <select className='input max-w-xs' value={sortBy} onChange={e=>setSortBy(e.target.value as any)}><option value='metric'>Sort by metric</option><option value='cathode'>Sort by cathode</option></select>
        </div>
        <div className='h-96'>
          <ResponsiveContainer width='100%' height='100%'>
            <BarChart data={perCathodeSorted}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='cathode_id' /><YAxis /><Tooltip /><Bar dataKey={metricForChart} fill='#2563eb' /></BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {Object.keys(result.timeseries || {}).length > 0 && <section className='card space-y-2'>
        <h3 className='font-semibold'>Trend over Time</h3>
        <div className='flex gap-2 flex-wrap'>
          {Object.keys(result.timeseries).slice(0, 20).map(c=>
            <label key={c} className='text-xs flex items-center gap-1'><input type='checkbox' checked={selectedCathodes.includes(c)} onChange={e=>setSelectedCathodes(e.target.checked ? [...selectedCathodes,c] : selectedCathodes.filter(x=>x!==c))}/>{c}</label>
          )}
        </div>
        <div className='h-96'>
          <ResponsiveContainer width='100%' height='100%'>
            <LineChart data={trendData}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='ts' /><YAxis /><Tooltip />
              {selectedCathodes.map((c, idx)=><Line key={c} type='monotone' dataKey={`${c}_${metricForChart}`} dot={false} stroke={['#2563eb','#7c3aed','#0d9488','#db2777'][idx%4]} />)}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>}

      <section className='card space-y-2 overflow-auto'>
        <h3 className='font-semibold'>Heatmap-style table</h3>
        <table className='min-w-full text-sm'>
          <thead><tr className='text-left border-b'><th className='p-2'>Cathode</th>{metricOptions.map(m=><th key={m} className='p-2'>{m}</th>)}</tr></thead>
          <tbody>
            {perCathodeSorted.map((row:any) => (
              <tr key={row.cathode_id} className='border-b hover:bg-slate-50 cursor-pointer' onClick={()=>setSelectedCathodes([row.cathode_id])}>
                <td className='p-2 font-medium'>{row.cathode_id}</td>
                {metricOptions.map(m=>{
                  const vals = perCathodeSorted.map((x:any)=>Number(x[m] ?? 0))
                  const v = Number(row[m] ?? 0)
                  return <td key={m} className='p-2' style={{ backgroundColor: quantileColor(v, vals) }}>{v.toFixed(4)}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className='card flex gap-2'>
        <button className='btn-secondary' onClick={()=>exportData('csv')}>Export CSV</button>
        <button className='btn-secondary' onClick={()=>exportData('json')}>Export JSON</button>
      </section>
    </>}
  </div>
}
