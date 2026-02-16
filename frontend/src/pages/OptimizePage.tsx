import { Copy, Download, Play, Save } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { Alert, Badge, Button, Card, Input, Progress, Select, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'
import { runJob } from '../lib/jobs'

type PlateRow = { plate: string; ts?: string; product?: string; thickness?: string }
type KnobSpec = { current: number; min: number; max: number; max_step: number }
type SavedRun = { id: string; ts: string; plateId: string; product?: string; inSpec?: boolean; score?: number; result: any; payload: any }

const empty = { L: 0, a: 0, b: 0 }

function pct(before: number, after: number) {
  const b = Number(before || 0)
  if (Math.abs(b) < 1e-9) return '—'
  return `${(((after - b) / b) * 100).toFixed(1)}%`
}

export function OptimizePage() {
  const { datasetId, globalFilters } = useDataset()
  const [plates, setPlates] = useState<PlateRow[]>([])
  const [search, setSearch] = useState('')
  const [plateId, setPlateId] = useState('')
  const [device, setDevice] = useState<'RG' | 'RF' | 'T'>('RG')
  const [mode, setMode] = useState<'target' | 'uniformity_in_spec'>('uniformity_in_spec')
  const [metricGroup, setMetricGroup] = useState<'lab' | 'b_only'>('b_only')
  const [baselineSource, setBaselineSource] = useState<'actual' | 'nearest_neighbor' | 'median_product'>('actual')
  const [target, setTarget] = useState({ ...empty })
  const [tol, setTol] = useState({ ...empty })
  const [tolDeltaE, setTolDeltaE] = useState<number | ''>('')
  const [activeThreshold, setActiveThreshold] = useState(0)
  const [lambdaKnob, setLambdaKnob] = useState(0.2)
  const [lambdaSmooth, setLambdaSmooth] = useState(0.1)
  const [wStdA, setWStdA] = useState(1)
  const [wStdB, setWStdB] = useState(1)
  const [wRangeA, setWRangeA] = useState(1)
  const [wRangeB, setWRangeB] = useState(1)
  const [wSmoothness, setWSmoothness] = useState(0.1)
  const [wDelta, setWDelta] = useState(0.2)
  const [robEnabled, setRobEnabled] = useState(true)
  const [robJitter, setRobJitter] = useState(1)
  const [robN, setRobN] = useState(200)
  const [maxTotalChange, setMaxTotalChange] = useState<number | ''>('')
  const [stgSeg, setStgSeg] = useState(true)
  const [stgPower, setStgPower] = useState(true)
  const [stgMain, setStgMain] = useState(false)
  const [coupling, setCoupling] = useState<'segmented_only' | 'main_plus_scale_segmented' | 'segmented_le_main' | 'segmented_eq_main'>('segmented_only')
  const [maxStepPct, setMaxStepPct] = useState<number | ''>('')
  const [measurementSource, setMeasurementSource] = useState<'last_plate' | 'median_n' | 'stable_window'>('last_plate')
  const [settleMode, setSettleMode] = useState<'immediate' | 'after_settle'>('immediate')
  const [ignoreOutliers, setIgnoreOutliers] = useState(false)
  const [predInterval, setPredInterval] = useState(false)

  const [actual, setActual] = useState<any>(null)
  const [baseline, setBaseline] = useState<any>(null)
  const [knobSchema, setKnobSchema] = useState<any>(null)
  const [logicalKnobs, setLogicalKnobs] = useState<any>({ gases_main: {}, gases_segmented: {} })
  const [result, setResult] = useState<any>(null)
  const [history, setHistory] = useState<SavedRun[]>([])
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [saveAnyway, setSaveAnyway] = useState(false)

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')

  useEffect(() => {
    const raw = localStorage.getItem('optimize_history')
    if (raw) {
      try { setHistory(JSON.parse(raw)) } catch { /* noop */ }
    }
  }, [])

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
      ;(ks?.gases_segmented?.entities || []).forEach((entity: string) => {
        segmented[entity] = {}
        ;['main1', 'main2', 'main3'].forEach((k) => {
          const col = ks?.gases_segmented?.cols?.[entity]?.[k]
          if (col) segmented[entity][k] = defaultEntry(col)
        })
      })

      setLogicalKnobs({ gases_main: main, gases_segmented: segmented, segmented_mode: ks?.gases_segmented?.mode || 'none' })
    }).catch(() => {
      setKnobSchema(null)
      setBaseline(null)
      setLogicalKnobs({ gases_main: {}, gases_segmented: {} })
    })
  }, [datasetId, plateId, device])

  const filteredPlates = useMemo(() => plates.filter((p) => `${p.plate} ${p.product || ''} ${p.ts || ''} ${p.thickness || ''}`.toLowerCase().includes(search.toLowerCase())), [plates, search])

  const buildPayload = () => ({
    dataset_id: datasetId,
    plate_id: plateId,
    device,
    mode,
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
    spec: { a_rg: { min: 2, max: 6 }, b_rg: { min: -4, max: 0 } },
    objective: { w_std_a: wStdA, w_std_b: wStdB, w_range_a: wRangeA, w_range_b: wRangeB, w_smoothness: wSmoothness, w_delta: wDelta },
    strategy: {
      gas_coupling: coupling,
      stages: [
        { name: 'segmented_gases', enabled: stgSeg },
        { name: 'cathode_power', enabled: stgPower },
        { name: 'main_gases', enabled: stgMain },
      ],
    },
    robustness: { enabled: robEnabled, jitter_pct: robJitter, n_simulations: robN },
    guardrails: { max_step_pct: maxStepPct === '' ? null : Number(maxStepPct), max_total_change: maxTotalChange === '' ? null : Number(maxTotalChange), on_only_cathodes: true },
    measurement: { source: measurementSource, median_n: 5, stable_window_n: 5, settle_mode: settleMode, ignore_outliers: ignoreOutliers, prediction_interval: predInterval },
  })

  const run = async () => {
    if (!datasetId || !plateId) { setError('Select plate and dataset first'); return }
    setLoading(true); setError('')
    try {
      const payload = buildPayload()
      const res = await runJob('/api/optimize', payload, ({ progress, stage }) => { setProgress(progress); setStage(stage) })
      setResult(res)
    } catch (e: any) { setError(e.message || 'Optimization failed') } finally { setLoading(false) }
  }

  const saveRun = () => {
    if (!result) return
    if (!result?.validity?.in_spec && !saveAnyway) return
    const run: SavedRun = {
      id: `${Date.now()}`,
      ts: new Date().toISOString(),
      plateId,
      product: globalFilters.products[0] || '',
      inSpec: !!result?.validity?.in_spec,
      score: result?.meta?.best_score,
      result,
      payload: buildPayload(),
    }
    const next = [run, ...history].slice(0, 20)
    setHistory(next)
    localStorage.setItem('optimize_history', JSON.stringify(next))
  }

  const copyDeltas = async () => {
    const txt = JSON.stringify(result?.recommendation || result?.knob_changes || {}, null, 2)
    await navigator.clipboard.writeText(txt)
  }

  const exportJson = () => {
    if (!result) return
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([JSON.stringify({ payload: buildPayload(), result }, null, 2)], { type: 'application/json' }))
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

  const aRows = useMemo(() => {
    const b = result?.before?.profiles?.a || actual?.a_points || []
    const p = result?.after?.profiles_pred?.a || []
    const cmp = compareIds.map((id) => history.find((h) => h.id === id)?.result?.after?.profiles_pred?.a || [])
    return (b || []).map((v: number, i: number) => ({
      pos: `p${i + 1}`,
      actual: v,
      predicted: p[i],
      c1: cmp[0]?.[i],
      c2: cmp[1]?.[i],
      low: 2,
      high: 6,
    }))
  }, [result, actual, compareIds, history])

  const bRows = useMemo(() => {
    const b = result?.before?.profiles?.b || actual?.b_points || []
    const p = result?.after?.profiles_pred?.b || []
    const cmp = compareIds.map((id) => history.find((h) => h.id === id)?.result?.after?.profiles_pred?.b || [])
    return (b || []).map((v: number, i: number) => ({
      pos: `p${i + 1}`,
      actual: v,
      predicted: p[i],
      c1: cmp[0]?.[i],
      c2: cmp[1]?.[i],
      low: -4,
      high: 0,
    }))
  }, [result, actual, compareIds, history])

  const domain = result?.domain_score?.label || 'in_domain'

  return <div className='space-y-6'>
    {!datasetId && <Alert variant='destructive'>Load data first.</Alert>}

    <Card className='space-y-3'>
      <div className='flex items-center justify-between'>
        <h3 className='text-sm font-medium tracking-tight'>Optimize</h3>
        <div className='flex items-center gap-2'>
          <span className='text-xs text-slate-500'>Mode</span>
          <Select value={mode} onChange={(e: any) => setMode(e.target.value)}>
            <option value='target'>Hit Target</option>
            <option value='uniformity_in_spec'>Improve Uniformity (in-spec)</option>
          </Select>
          {mode === 'uniformity_in_spec' && <Badge className='bg-red-100 text-red-700'>Hard constraints ON</Badge>}
        </div>
      </div>
      {mode === 'uniformity_in_spec' && <Alert>a:[2,6], b:[-4,0] per position (RG profile)</Alert>}
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
      <h3 className='text-sm font-medium tracking-tight'>Objective + guardrails</h3>
      <div className='grid md:grid-cols-4 gap-2'>
        <div><label className='text-xs'>w_std_a</label><Input type='number' value={wStdA} onChange={(e: any) => setWStdA(Number(e.target.value))} /></div>
        <div><label className='text-xs'>w_std_b</label><Input type='number' value={wStdB} onChange={(e: any) => setWStdB(Number(e.target.value))} /></div>
        <div><label className='text-xs'>w_range_a</label><Input type='number' value={wRangeA} onChange={(e: any) => setWRangeA(Number(e.target.value))} /></div>
        <div><label className='text-xs'>w_range_b</label><Input type='number' value={wRangeB} onChange={(e: any) => setWRangeB(Number(e.target.value))} /></div>
        <div><label className='text-xs'>w_smoothness</label><Input type='number' value={wSmoothness} onChange={(e: any) => setWSmoothness(Number(e.target.value))} /></div>
        <div><label className='text-xs'>w_delta</label><Input type='number' value={wDelta} onChange={(e: any) => setWDelta(Number(e.target.value))} /></div>
        <div><label className='text-xs'>max_total_change</label><Input type='number' value={maxTotalChange} onChange={(e: any) => setMaxTotalChange(e.target.value === '' ? '' : Number(e.target.value))} /></div>
      </div>
      <div className='grid md:grid-cols-3 gap-2'>
        <label className='text-sm'><input type='checkbox' checked={stgSeg} onChange={(e) => setStgSeg(e.target.checked)} /> Stage 1 segmented gases</label>
        <label className='text-sm'><input type='checkbox' checked={stgPower} onChange={(e) => setStgPower(e.target.checked)} /> Stage 2 cathode power</label>
        <label className='text-sm'><input type='checkbox' checked={stgMain} onChange={(e) => setStgMain(e.target.checked)} /> Stage 3 main gases</label>
      </div>
      <div className='grid md:grid-cols-4 gap-2'>
        <div><label className='text-xs'>Coupling</label><Select value={coupling} onChange={(e: any) => setCoupling(e.target.value)}><option value='segmented_only'>segmented_only</option><option value='main_plus_scale_segmented'>main_plus_scale_segmented</option><option value='segmented_le_main'>segmented_le_main</option><option value='segmented_eq_main'>segmented_eq_main</option></Select></div>
        <div><label className='text-xs'>max_step_pct</label><Input type='number' value={maxStepPct} onChange={(e: any) => setMaxStepPct(e.target.value === '' ? '' : Number(e.target.value))} /></div>
        <div><label className='text-xs'>Measurement source</label><Select value={measurementSource} onChange={(e: any) => setMeasurementSource(e.target.value)}><option value='last_plate'>last_plate</option><option value='median_n'>median_n</option><option value='stable_window'>stable_window</option></Select></div>
        <div><label className='text-xs'>Settle mode</label><Select value={settleMode} onChange={(e: any) => setSettleMode(e.target.value)}><option value='immediate'>immediate</option><option value='after_settle'>after_settle</option></Select></div>
      </div>
      <div className='grid md:grid-cols-3 gap-2'>
        <label className='text-sm'><input type='checkbox' checked={ignoreOutliers} onChange={(e) => setIgnoreOutliers(e.target.checked)} /> Ignore outliers</label>
        <label className='text-sm'><input type='checkbox' checked={predInterval} onChange={(e) => setPredInterval(e.target.checked)} /> Prediction interval</label>
      </div>
      <div className='grid md:grid-cols-3 gap-2'>
        <label className='text-sm'><input type='checkbox' checked={robEnabled} onChange={(e) => setRobEnabled(e.target.checked)} /> Robustness check</label>
        <div><label className='text-xs'>jitter %</label><Input type='number' value={robJitter} onChange={(e: any) => setRobJitter(Number(e.target.value))} /></div>
        <div><label className='text-xs'>n simulations</label><Input type='number' value={robN} onChange={(e: any) => setRobN(Number(e.target.value))} /></div>
      </div>
    </Card>

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Knobs (auto-discovered)</h3>
      <h4 className='text-sm font-medium'>Main gases</h4>
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

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Run + status</h3>
      {loading && <><Progress value={progress} /><p className='text-sm text-slate-500'>{stage}</p></>}
      {error && <Alert variant='destructive'>{error}</Alert>}
      <div className='flex flex-wrap gap-2 items-center'>
        <Button onClick={run} disabled={!datasetId || !plateId || loading}><Play size={16} className='inline mr-1' />Run optimization</Button>
        <Badge className={domain === 'in_domain' ? 'bg-emerald-100 text-emerald-700' : domain === 'borderline' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}>
          Model validity: {domain}
        </Badge>
        {result?.domain_score?.score !== undefined && <span className='text-sm text-slate-500'>score={Number(result.domain_score.score).toFixed(3)}</span>}
      </div>
      {domain === 'out_of_domain' && <Alert variant='destructive'>Out-of-domain recommendation. Confirm before applying/saving.</Alert>}
    </Card>

    {!actual && plateId && <div className='grid md:grid-cols-3 gap-3'>{[1, 2, 3].map((i) => <Skeleton key={i} className='h-20' />)}</div>}

    {result && <>
      <Card className='space-y-3'>
        <h3 className='text-sm font-medium tracking-tight'>Before → After KPIs</h3>
        <div className='grid md:grid-cols-4 gap-2 text-sm'>
          <Card className='p-2'>std_a: {result.before?.std_a?.toFixed?.(4) ?? '—'} → {result.after?.std_a?.toFixed?.(4) ?? '—'} ({pct(result.before?.std_a, result.after?.std_a)})</Card>
          <Card className='p-2'>std_b: {result.before?.std_b?.toFixed?.(4) ?? '—'} → {result.after?.std_b?.toFixed?.(4) ?? '—'} ({pct(result.before?.std_b, result.after?.std_b)})</Card>
          <Card className='p-2'>range_a: {result.before?.range_a?.toFixed?.(4) ?? '—'} → {result.after?.range_a?.toFixed?.(4) ?? '—'} ({pct(result.before?.range_a, result.after?.range_a)})</Card>
          <Card className='p-2'>range_b: {result.before?.range_b?.toFixed?.(4) ?? '—'} → {result.after?.range_b?.toFixed?.(4) ?? '—'} ({pct(result.before?.range_b, result.after?.range_b)})</Card>
          <Card className='p-2'>worst a: p{result.before?.worst_a?.pos} → p{result.after?.worst_a?.pos}</Card>
          <Card className='p-2'>worst b: p{result.before?.worst_b?.pos} → p{result.after?.worst_b?.pos}</Card>
          <Card className='p-2'><Badge className={result.validity?.in_spec ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}>{result.validity?.in_spec ? 'All positions in spec after apply' : 'Out of spec after apply'}</Badge></Card>
        </div>
        <div className='flex gap-2 items-center text-sm'>
          <Badge className={result.measurement_quality?.label === 'good' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>Measurement: {result.measurement_quality?.label || 'unknown'}</Badge>
          <span>Outliers: {(result.measurement_quality?.outliers || []).length}</span>
        </div>
        {!!(result.measurement_quality?.outliers || []).length && <Alert>Outliers: {(result.measurement_quality?.outliers || []).map((o: any) => `${o.metric} p${o.pos} z=${Number(o.z).toFixed(2)}`).join('; ')}</Alert>}
        {!!(result.validity?.violations || []).length && <Alert variant='destructive'>{(result.validity?.violations || []).map((v: any) => `${v.metric} p${v.pos}=${Number(v.value).toFixed(3)} not in [${v.min},${v.max}]`).join('; ')}</Alert>}
      </Card>

      <Card className='space-y-3'>
        <h3 className='text-sm font-medium tracking-tight'>Profiles (a / b) with spec bands</h3>
        <Card className='h-64'>
          <ResponsiveContainer width='100%' height='100%'>
            <AreaChart data={aRows}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='pos' /><YAxis /><Tooltip /><Legend />
              <Area type='monotone' dataKey='high' stroke='none' fill='#dcfce7' name='spec max' />
              <Area type='monotone' dataKey='low' stroke='none' fill='#dcfce7' name='spec min' />
              <Line type='monotone' dataKey='actual' stroke='#2563eb' name='Actual' />
              <Line type='monotone' dataKey='predicted' stroke='#16a34a' name='Predicted after apply' />
              {compareIds[0] && <Line type='monotone' dataKey='c1' stroke='#7c3aed' name='Compare 1' />}
              {compareIds[1] && <Line type='monotone' dataKey='c2' stroke='#ea580c' name='Compare 2' />}
            </AreaChart>
          </ResponsiveContainer>
        </Card>
        <Card className='h-64'>
          <ResponsiveContainer width='100%' height='100%'>
            <AreaChart data={bRows}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='pos' /><YAxis /><Tooltip /><Legend />
              <Area type='monotone' dataKey='high' stroke='none' fill='#dcfce7' name='spec max' />
              <Area type='monotone' dataKey='low' stroke='none' fill='#dcfce7' name='spec min' />
              <Line type='monotone' dataKey='actual' stroke='#2563eb' name='Actual' />
              <Line type='monotone' dataKey='predicted' stroke='#16a34a' name='Predicted after apply' />
              {compareIds[0] && <Line type='monotone' dataKey='c1' stroke='#7c3aed' name='Compare 1' />}
              {compareIds[1] && <Line type='monotone' dataKey='c2' stroke='#ea580c' name='Compare 2' />}
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </Card>

      <Card className='space-y-2'>
        <h3 className='text-sm font-medium tracking-tight'>Robustness + actions</h3>
        {result.robustness && <div className='grid md:grid-cols-2 gap-2 text-sm'>
          <Card className='p-2'>P(in spec): {(Number(result.robustness.p_in_spec || 0) * 100).toFixed(1)}%</Card>
          <Card className='p-2'>P(improve uniformity): {(Number(result.robustness.p_improve_uniformity || 0) * 100).toFixed(1)}%</Card>
        </div>}
        <div className='flex flex-wrap gap-2'>
          <Button variant='secondary' onClick={exportCsv}><Download size={16} className='inline mr-1' />Export CSV</Button>
          <Button variant='secondary' onClick={exportJson}><Download size={16} className='inline mr-1' />Export JSON</Button>
          <Button variant='secondary' onClick={copyDeltas}><Copy size={16} className='inline mr-1' />Copy deltas</Button>
          <label className='text-sm ml-2'><input type='checkbox' checked={saveAnyway} onChange={(e) => setSaveAnyway(e.target.checked)} /> Save anyway</label>
          <Button onClick={saveRun} disabled={!result?.validity?.in_spec && !saveAnyway}><Save size={16} className='inline mr-1' />Save run</Button>
        </div>
      </Card>
    </>}

    <Card className='space-y-2'>
      <h3 className='text-sm font-medium tracking-tight'>History + Compare</h3>
      {history.length === 0 && <p className='text-sm text-slate-500'>No saved runs yet.</p>}
      {history.map((h) => <div key={h.id} className='border rounded p-2 text-sm flex flex-wrap items-center gap-2'>
        <span>{new Date(h.ts).toLocaleString()}</span>
        <span>plate={h.plateId}</span>
        <span>score={h.score ?? '—'}</span>
        <Badge className={h.inSpec ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}>{h.inSpec ? 'in_spec' : 'out_spec'}</Badge>
        <Button variant='secondary' onClick={() => setResult(h.result)}>Load</Button>
        <label><input type='checkbox' checked={compareIds.includes(h.id)} onChange={(e) => setCompareIds((prev) => e.target.checked ? [...new Set([...prev, h.id])].slice(0, 2) : prev.filter((x) => x !== h.id))} /> Compare</label>
      </div>)}
    </Card>
  </div>
}
