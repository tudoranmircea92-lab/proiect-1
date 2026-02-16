import { Download, Play } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { Alert, Badge, Button, Card, Input, Progress, Select, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'
import { runJob } from '../lib/jobs'

type PlateRow = { plate: string; ts?: string; product?: string; thickness?: string }

const empty = { L: 0, a: 0, b: 0 }

export function OptimizePage() {
  const { datasetId, globalFilters } = useDataset()
  const [plates, setPlates] = useState<PlateRow[]>([])
  const [search, setSearch] = useState('')
  const [plateId, setPlateId] = useState('')
  const [device, setDevice] = useState<'RG' | 'RF' | 'T'>('RG')
  const [metricGroup, setMetricGroup] = useState<'lab' | 'b_only'>('b_only')
  const [baselineSource, setBaselineSource] = useState<'actual' | 'nearest_neighbor' | 'median_product'>('actual')
  const [target, setTarget] = useState({ ...empty })
  const [tol, setTol] = useState({ ...empty })
  const [tolDeltaE, setTolDeltaE] = useState<number | ''>('')
  const [channel, setChannel] = useState<'L' | 'a' | 'b'>('b')
  const [activeThreshold, setActiveThreshold] = useState(0)
  const [lambdaKnob, setLambdaKnob] = useState(0.2)
  const [lambdaSmooth, setLambdaSmooth] = useState(0.1)
  const [actual, setActual] = useState<any>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')

  useEffect(() => {
    if (!datasetId) return
    const product = globalFilters.products[0] || ''
    const thickness = globalFilters.thicknesses[0] || ''
    const q = new URLSearchParams({ dataset_id: datasetId, limit: '500' })
    if (product) q.set('product', product)
    if (thickness) q.set('thickness', thickness)
    if (globalFilters.dateFrom) q.set('date_from', globalFilters.dateFrom)
    if (globalFilters.dateTo) q.set('date_to', globalFilters.dateTo)
    api.get(`/api/plates?${q.toString()}`).then((r) => setPlates(r.data.rows || []))
  }, [datasetId, globalFilters])

  useEffect(() => {
    if (!datasetId || !plateId) return
    api.get(`/api/plate/${encodeURIComponent(plateId)}/color?dataset_id=${datasetId}&device=${device}`).then((r) => setActual(r.data)).catch(() => setActual(null))
  }, [datasetId, plateId, device])

  const filteredPlates = useMemo(() => plates.filter((p) => `${p.plate} ${p.product || ''} ${p.ts || ''} ${p.thickness || ''}`.toLowerCase().includes(search.toLowerCase())), [plates, search])

  const run = async () => {
    if (!datasetId || !plateId) { setError('Select plate and dataset first'); return }
    setLoading(true); setError('')
    try {
      const payload = {
        dataset_id: datasetId,
        plate_id: plateId,
        device,
        metric_group: metricGroup,
        baseline_source: baselineSource,
        targets: target,
        tolerances: tol,
        tol_deltaE: tolDeltaE === '' ? null : Number(tolDeltaE),
        active_threshold: activeThreshold,
        knob_groups: { power: true, main_gas: true, segment_gas: true },
        lambda_knob_change: lambdaKnob,
        lambda_smoothness: lambdaSmooth,
        method: 'search',
        params: { k_neighbors: 5, n_iterations: 400, n_solutions: 1, device_weights: { RG: 1, RF: 1, T: 1 } },
        bounds: { pwr_pct: 8, gas_pct: 8 },
        filter: { products: globalFilters.products, thicknesses: globalFilters.thicknesses, date_from: globalFilters.dateFrom || null, date_to: globalFilters.dateTo || null },
      }
      const res = await runJob('/api/optimize', payload, ({ progress, stage }) => { setProgress(progress); setStage(stage) })
      setResult(res)
    } catch (e: any) { setError(e.message || 'Optimization failed') } finally { setLoading(false) }
  }

  const chartRows = useMemo(() => {
    const pts = actual?.[`${channel}_points`] || []
    const mean = actual?.[`${channel}_mean`]
    const before = result?.baseline_pred?.[channel]
    const after = result?.optimized_pred?.[channel]
    if (pts.length) {
      return pts.map((v: number, i: number) => ({ pos: `p${i + 1}`, actual: v, mean, pred_before: before, pred_after: after }))
    }
    return [{ pos: 'mean', actual: mean, mean, pred_before: before, pred_after: after }]
  }, [actual, result, channel])

  const exportJson = () => {
    if (!result) return
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }))
    a.download = 'optimization_report.json'
    a.click()
  }

  const exportCsv = () => {
    if (!result) return
    const rows = [['group', 'knob', 'baseline', 'optimized', 'delta', 'min', 'max']]
    Object.entries(result.knob_changes || {}).forEach(([g, arr]: any) => arr.forEach((r: any) => rows.push([g, r.knob, r.baseline, r.optimized, r.delta, r.bound_min, r.bound_max])))
    const csv = rows.map((r) => r.join(',')).join('\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    a.download = 'optimization_changes.csv'
    a.click()
  }

  return <div className='space-y-6'>
    {!datasetId && <Alert variant='destructive'>Load data first.</Alert>}

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>1) Selection</h3>
      <div className='grid md:grid-cols-3 gap-3'>
        <div className='space-y-1'>
          <label className='text-sm'>Search plate</label>
          <Input value={search} onChange={(e: any) => setSearch(e.target.value)} placeholder='plate / product / ts' />
        </div>
        <div className='space-y-1'>
          <label className='text-sm'>Plate</label>
          <Select value={plateId} onChange={(e: any) => setPlateId(e.target.value)}>
            <option value=''>Select plate</option>
            {filteredPlates.map((p) => <option key={p.plate} value={p.plate}>{p.plate} • {p.ts || '-'} • {p.product || '-'} • {p.thickness || '-'}</option>)}
          </Select>
        </div>
        <div className='grid grid-cols-2 gap-2'>
          <div><label className='text-sm'>Device</label><Select value={device} onChange={(e: any) => setDevice(e.target.value)}><option value='RG'>RG</option><option value='RF'>RF</option><option value='T'>T</option></Select></div>
          <div><label className='text-sm'>Metric group</label><Select value={metricGroup} onChange={(e: any) => setMetricGroup(e.target.value)}><option value='b_only'>b only</option><option value='lab'>L/a/b</option></Select></div>
        </div>
      </div>
      <div className='grid md:grid-cols-2 gap-2'>
        <div><label className='text-sm'>Baseline source</label><Select value={baselineSource} onChange={(e: any) => setBaselineSource(e.target.value)}><option value='actual'>Use actual plate knobs</option><option value='nearest_neighbor'>Nearest neighbor baseline</option><option value='median_product'>Median baseline for same product</option></Select></div>
        <div><label className='text-sm'>Active threshold (power)</label><Input type='number' value={activeThreshold} onChange={(e: any) => setActiveThreshold(Number(e.target.value))} /></div>
      </div>
    </Card>

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>2) Targets & tolerances</h3>
      <div className='grid md:grid-cols-3 gap-3'>
        {metricGroup === 'b_only' ? <><div><label className='text-sm'>b target</label><Input type='number' value={target.b} onChange={(e: any) => setTarget({ ...target, b: Number(e.target.value) })} /></div><div><label className='text-sm'>tol_b</label><Input type='number' value={tol.b} onChange={(e: any) => setTol({ ...tol, b: Number(e.target.value) })} /></div></> : (['L', 'a', 'b'] as const).map((ch) => <div key={ch}><label className='text-sm'>{ch} target / tol</label><div className='flex gap-2'><Input type='number' value={(target as any)[ch]} onChange={(e: any) => setTarget({ ...target, [ch]: Number(e.target.value) })} /><Input type='number' value={(tol as any)[ch]} onChange={(e: any) => setTol({ ...tol, [ch]: Number(e.target.value) })} /></div></div>)}
        <div><label className='text-sm'>tol_deltaE (optional)</label><Input type='number' value={tolDeltaE} onChange={(e: any) => setTolDeltaE(e.target.value === '' ? '' : Number(e.target.value))} /></div>
      </div>
      <div className='grid md:grid-cols-3 gap-2'>
        <div className='text-sm border rounded p-2'>Actual L: {actual?.L_mean ?? '—'}</div>
        <div className='text-sm border rounded p-2'>Actual a: {actual?.a_mean ?? '—'}</div>
        <div className='text-sm border rounded p-2'>Actual b: {actual?.b_mean ?? '—'}</div>
      </div>
      <details>
        <summary className='text-sm cursor-pointer'>Advanced penalties</summary>
        <div className='grid md:grid-cols-2 gap-3 mt-2'>
          <div><label className='text-sm'>lambda_knob_change</label><Input type='number' step='0.05' value={lambdaKnob} onChange={(e: any) => setLambdaKnob(Number(e.target.value))} /></div>
          <div><label className='text-sm'>lambda_smoothness</label><Input type='number' step='0.05' value={lambdaSmooth} onChange={(e: any) => setLambdaSmooth(Number(e.target.value))} /></div>
        </div>
      </details>
    </Card>

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>3) Run + Results</h3>
      {loading && <><Progress value={progress} /><p className='text-sm text-slate-500'>{stage}</p></>}
      {error && <Alert variant='destructive'>{error}</Alert>}
      <Button onClick={run} disabled={!datasetId || !plateId || loading}><Play size={16} className='inline mr-1' />Run optimization</Button>
    </Card>

    {!actual && plateId && <div className='grid md:grid-cols-3 gap-3'>{[1, 2, 3].map((i) => <Skeleton key={i} className='h-20' />)}</div>}

    {actual && <Card className='space-y-3'>
      <div className='flex items-center justify-between'>
        <h3 className='text-sm font-medium tracking-tight'>Actual measured color ({device})</h3>
        <div className='flex gap-2'>
          <Badge>L μ={actual.L_mean ?? '—'} σ={actual.L_std ?? '—'}</Badge>
          <Badge>a μ={actual.a_mean ?? '—'} σ={actual.a_std ?? '—'}</Badge>
          <Badge>b μ={actual.b_mean ?? '—'} σ={actual.b_std ?? '—'}</Badge>
        </div>
      </div>
      <div className='flex gap-2'>
        <Button variant={channel === 'L' ? 'default' : 'secondary'} onClick={() => setChannel('L')}>L</Button>
        <Button variant={channel === 'a' ? 'default' : 'secondary'} onClick={() => setChannel('a')}>a</Button>
        <Button variant={channel === 'b' ? 'default' : 'secondary'} onClick={() => setChannel('b')}>b</Button>
      </div>
      {(actual[`${channel}_points`] || []).length ? (
        <Card className='h-72'>
          <ResponsiveContainer width='100%' height='100%'>
            <LineChart data={chartRows}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='pos' /><YAxis /><Tooltip /><Legend />
              <Line type='monotone' dataKey='actual' stroke='#2563eb' name='Actual measured' />
              <Line type='monotone' dataKey='mean' stroke='#0f766e' strokeDasharray='5 5' name='Actual mean' />
              {result && <Line type='monotone' dataKey='pred_before' stroke='#b45309' name='Pred baseline' />}
              {result && <Line type='monotone' dataKey='pred_after' stroke='#16a34a' name='Pred optimized' />}
            </LineChart>
          </ResponsiveContainer>
        </Card>
      ) : <Alert>positions not available</Alert>}
    </Card>}

    {result && <>
      <Card className='space-y-3'>
        <h3 className='text-sm font-medium tracking-tight'>Before vs After</h3>
        <div className='grid md:grid-cols-3 gap-2 text-sm'>
          <Card className='p-3'>Actual baseline: L {result.baseline_actual?.L ?? '—'} / a {result.baseline_actual?.a ?? '—'} / b {result.baseline_actual?.b ?? '—'}</Card>
          <Card className='p-3'>Pred baseline: L {result.baseline_pred?.L ?? '—'} / a {result.baseline_pred?.a ?? '—'} / b {result.baseline_pred?.b ?? '—'}</Card>
          <Card className='p-3'>Pred optimized: L {result.optimized_pred?.L ?? '—'} / a {result.optimized_pred?.a ?? '—'} / b {result.optimized_pred?.b ?? '—'}</Card>
        </div>
        <p className='text-sm text-slate-600'>Diagnostics: iterations={result.diagnostics?.iterations} best_loss={Number(result.diagnostics?.best_loss ?? 0).toFixed(6)}</p>
      </Card>

      <Card className='space-y-2'>
        <h3 className='text-sm font-medium tracking-tight'>Recommended knob changes</h3>
        {Object.entries(result.knob_changes || {}).map(([g, arr]: any) => <div key={g}><p className='text-sm font-medium'>{g}</p><table className='min-w-full text-sm'><thead><tr className='border-b'><th className='p-2 text-left'>Knob</th><th className='p-2 text-left'>Baseline</th><th className='p-2 text-left'>Optimized</th><th className='p-2 text-left'>Δ</th><th className='p-2 text-left'>Bounds</th></tr></thead><tbody>{arr.map((r: any) => <tr key={r.knob} className='border-b'><td className='p-2'>{r.knob}</td><td className='p-2'>{r.baseline.toFixed(4)}</td><td className='p-2'>{r.optimized.toFixed(4)}</td><td className='p-2'>{r.delta.toFixed(4)}</td><td className='p-2'>[{r.bound_min.toFixed(4)}, {r.bound_max.toFixed(4)}]</td></tr>)}</tbody></table></div>)}
        <div className='flex gap-2'>
          <Button variant='secondary' onClick={exportCsv}><Download size={16} className='inline mr-1' />Export CSV</Button>
          <Button variant='secondary' onClick={exportJson}><Download size={16} className='inline mr-1' />Export JSON</Button>
        </div>
      </Card>
    </>}
  </div>
}
