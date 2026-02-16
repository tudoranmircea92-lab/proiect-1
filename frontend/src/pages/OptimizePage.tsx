import { Download, Play } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { Alert, Badge, Button, Card, Input, Progress, Select, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'
import { runJob } from '../lib/jobs'

type PlateRow = { plate: string; ts?: string; product?: string; thickness?: string }
type KnobSpec = { current: number; min: number; max: number; max_step: number }

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
  const [baseline, setBaseline] = useState<any>(null)
  const [knobSchema, setKnobSchema] = useState<any>(null)
  const [logicalKnobs, setLogicalKnobs] = useState<any>({ gases_main: {}, gases_segmented: {} })
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

    const q = new URLSearchParams({ dataset_id: datasetId, plate_id: plateId })
    api.get(`/api/optimize/context?${q.toString()}`).then((r) => {
      const ks = r.data?.knob_schema || null
      const base = r.data?.baseline || null
      setKnobSchema(ks)
      setBaseline(base)

      const baselineKnobs = base?.baseline_knobs || {}
      const defaultEntry = (col?: string): KnobSpec => {
        const cur = col ? Number(baselineKnobs[col] ?? 0) : 0
        const span = Math.max(Math.abs(cur) * 0.1, 1)
        return { current: cur, min: cur - span, max: cur + span, max_step: Math.max(span * 0.5, 0.1) }
      }

      const main: any = {}
      ;['main1', 'main2', 'main3'].forEach((k) => {
        const col = ks?.gases_main?.cols?.[k]
        if (col) main[k] = defaultEntry(col)
      })

      const segmented: any = {}
      const mode = ks?.gases_segmented?.mode
      ;(ks?.gases_segmented?.entities || []).forEach((entity: string) => {
        segmented[entity] = {}
        ;['main1', 'main2', 'main3'].forEach((k) => {
          const col = ks?.gases_segmented?.cols?.[entity]?.[k]
          if (col) segmented[entity][k] = defaultEntry(col)
        })
      })

      setLogicalKnobs({ gases_main: main, gases_segmented: segmented, segmented_mode: mode || 'none' })
    }).catch(() => {
      setKnobSchema(null)
      setBaseline(null)
      setLogicalKnobs({ gases_main: {}, gases_segmented: {} })
    })
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
        knobs: logicalKnobs,
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
    a.download = 'optimization_knob_changes.csv'
    a.click()
  }

  const updateSpec = (scope: 'main' | 'seg', keyA: string, keyB: string | null, field: keyof KnobSpec, value: number) => {
    setLogicalKnobs((prev: any) => {
      const next = { ...(prev || {}) }
      if (scope === 'main') {
        next.gases_main = { ...(next.gases_main || {}) }
        next.gases_main[keyA] = { ...(next.gases_main?.[keyA] || { current: 0, min: 0, max: 0, max_step: 0 }), [field]: value }
      } else {
        next.gases_segmented = { ...(next.gases_segmented || {}) }
        next.gases_segmented[keyA] = { ...(next.gases_segmented?.[keyA] || {}) }
        const k = keyB || 'main1'
        next.gases_segmented[keyA][k] = { ...(next.gases_segmented?.[keyA]?.[k] || { current: 0, min: 0, max: 0, max_step: 0 }), [field]: value }
      }
      return next
    })
  }

  return <div className='space-y-6'>
    {!datasetId && <Alert variant='destructive'>Load data first.</Alert>}

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>1) Selection</h3>
      <div className='grid md:grid-cols-2 gap-3'>
        <div>
          <label className='text-sm'>Plate</label>
          <Input placeholder='Search plate/product/ts' value={search} onChange={(e: any) => setSearch(e.target.value)} />
          <Select value={plateId} onChange={(e: any) => setPlateId(e.target.value)}>
            <option value=''>Select plate</option>
            {filteredPlates.map((r) => <option key={r.plate} value={r.plate}>{r.plate} | {r.ts || '-'} | {r.product || '-'} | {r.thickness || '-'}</option>)}
          </Select>
        </div>
        <div className='grid grid-cols-2 gap-2'>
          <div><label className='text-sm'>Device</label><Select value={device} onChange={(e: any) => setDevice(e.target.value)}><option value='RG'>RG</option><option value='RF'>RF</option><option value='T'>T</option></Select></div>
          <div><label className='text-sm'>Output mode</label><Select value={metricGroup} onChange={(e: any) => setMetricGroup(e.target.value)}><option value='b_only'>b only</option><option value='lab'>L,a,b</option></Select></div>
          <div><label className='text-sm'>Baseline source</label><Select value={baselineSource} onChange={(e: any) => setBaselineSource(e.target.value)}><option value='actual'>Actual row</option><option value='nearest_neighbor'>Nearest neighbor</option><option value='median_product'>Median product</option></Select></div>
          <div><label className='text-sm'>Active threshold</label><Select value={String(activeThreshold)} onChange={(e: any) => setActiveThreshold(Number(e.target.value))}><option value='0'>0.0</option><option value='0.1'>0.1</option><option value='1'>1.0</option></Select></div>
        </div>
      </div>
    </Card>

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>2) Targets + tolerances</h3>
      <div className='grid md:grid-cols-3 gap-2'>
        <div><label className='text-sm'>Target L</label><Input type='number' value={target.L} onChange={(e: any) => setTarget((p) => ({ ...p, L: Number(e.target.value) }))} /></div>
        <div><label className='text-sm'>Target a</label><Input type='number' value={target.a} onChange={(e: any) => setTarget((p) => ({ ...p, a: Number(e.target.value) }))} /></div>
        <div><label className='text-sm'>Target b</label><Input type='number' value={target.b} onChange={(e: any) => setTarget((p) => ({ ...p, b: Number(e.target.value) }))} /></div>
      </div>
      <div className='grid md:grid-cols-4 gap-2'>
        <div><label className='text-sm'>tol_L</label><Input type='number' value={tol.L} onChange={(e: any) => setTol((p) => ({ ...p, L: Number(e.target.value) }))} /></div>
        <div><label className='text-sm'>tol_a</label><Input type='number' value={tol.a} onChange={(e: any) => setTol((p) => ({ ...p, a: Number(e.target.value) }))} /></div>
        <div><label className='text-sm'>tol_b</label><Input type='number' value={tol.b} onChange={(e: any) => setTol((p) => ({ ...p, b: Number(e.target.value) }))} /></div>
        <div><label className='text-sm'>tol_deltaE (optional)</label><Input type='number' value={tolDeltaE} onChange={(e: any) => setTolDeltaE(e.target.value === '' ? '' : Number(e.target.value))} /></div>
      </div>
      <div className='grid md:grid-cols-3 gap-2'>
        <div className='text-sm border rounded p-2'>Actual L: {actual?.L_mean ?? '—'}</div>
        <div className='text-sm border rounded p-2'>Actual a: {actual?.a_mean ?? '—'}</div>
        <div className='text-sm border rounded p-2'>Actual b: {actual?.b_mean ?? '—'}</div>
      </div>

      <Card className='space-y-2'>
        <h4 className='text-sm font-medium'>Main gases (auto-discovered)</h4>
        <div className='grid md:grid-cols-3 gap-2'>
          {['main1', 'main2', 'main3'].map((k) => {
            const col = knobSchema?.gases_main?.cols?.[k]
            const spec: KnobSpec = logicalKnobs?.gases_main?.[k] || { current: 0, min: 0, max: 0, max_step: 0 }
            return <Card key={k} className='p-2 space-y-1'>
              <p className='text-xs text-slate-500'>{k} → {col || 'not found'}</p>
              <Input type='number' value={spec.current} onChange={(e: any) => updateSpec('main', k, null, 'current', Number(e.target.value))} />
              <div className='grid grid-cols-3 gap-1'>
                <Input type='number' value={spec.min} onChange={(e: any) => updateSpec('main', k, null, 'min', Number(e.target.value))} />
                <Input type='number' value={spec.max} onChange={(e: any) => updateSpec('main', k, null, 'max', Number(e.target.value))} />
                <Input type='number' value={spec.max_step} onChange={(e: any) => updateSpec('main', k, null, 'max_step', Number(e.target.value))} />
              </div>
            </Card>
          })}
        </div>
      </Card>

      <Card className='space-y-2'>
        <h4 className='text-sm font-medium'>Segmented gases ({knobSchema?.gases_segmented?.mode || 'none'})</h4>
        {(knobSchema?.gases_segmented?.entities || []).length === 0 && <p className='text-sm text-slate-500'>No segmented gas entities detected.</p>}
        {(knobSchema?.gases_segmented?.entities || []).map((entity: string) => <div key={entity} className='border rounded p-2 space-y-1'>
          <p className='text-sm font-medium'>{entity}</p>
          <div className='grid md:grid-cols-3 gap-2'>
            {['main1', 'main2', 'main3'].map((k) => {
              const col = knobSchema?.gases_segmented?.cols?.[entity]?.[k]
              if (!col) return <Card key={k} className='p-2 text-xs text-slate-400'>{k}: n/a</Card>
              const spec: KnobSpec = logicalKnobs?.gases_segmented?.[entity]?.[k] || { current: 0, min: 0, max: 0, max_step: 0 }
              return <Card key={k} className='p-2 space-y-1'>
                <p className='text-xs text-slate-500'>{k} → {col}</p>
                <Input type='number' value={spec.current} onChange={(e: any) => updateSpec('seg', entity, k, 'current', Number(e.target.value))} />
                <div className='grid grid-cols-3 gap-1'>
                  <Input type='number' value={spec.min} onChange={(e: any) => updateSpec('seg', entity, k, 'min', Number(e.target.value))} />
                  <Input type='number' value={spec.max} onChange={(e: any) => updateSpec('seg', entity, k, 'max', Number(e.target.value))} />
                  <Input type='number' value={spec.max_step} onChange={(e: any) => updateSpec('seg', entity, k, 'max_step', Number(e.target.value))} />
                </div>
              </Card>
            })}
          </div>
        </div>)}
      </Card>

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
        {(result.diagnostics?.warnings || []).length > 0 && <Alert>{(result.diagnostics?.warnings || []).join('; ')}</Alert>}
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
