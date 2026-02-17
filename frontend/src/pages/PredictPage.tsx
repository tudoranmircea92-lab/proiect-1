import { Download, Play, RotateCcw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Accordion, Alert, Badge, Button, Card, Input, Progress, Select, Skeleton, Switch } from '../components/ui'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'
import { runJob } from '../lib/jobs'

type Device = 'RG' | 'RF' | 'T'
type OutputMode = 'b_only' | 'lab'

type SeedRow = { plate: string; ts?: string; product?: string; thickness?: string }

const KNOB_RE = /^(c\d+)\.(.*)$/i

function fmt(v: any, d = 4) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d)
}

function outputKeys(mode: OutputMode) {
  return mode === 'b_only' ? (['b'] as const) : (['L', 'a', 'b'] as const)
}

export function PredictPage() {
  const { datasetId, globalFilters, modelTrained } = useDataset()
  const [seedRows, setSeedRows] = useState<SeedRow[]>([])
  const [search, setSearch] = useState('')
  const [plateId, setPlateId] = useState('')
  const [device, setDevice] = useState<Device>('RG')
  const [outputs, setOutputs] = useState<OutputMode>('b_only')
  const [baseline, setBaseline] = useState<any>(null)
  const [editedKnobs, setEditedKnobs] = useState<Record<string, number>>({})
  const [activeOnly, setActiveOnly] = useState(true)
  const [useTarget, setUseTarget] = useState(false)
  const [target, setTarget] = useState({ L: 0, a: 0, b: 0 })
  const [tol, setTol] = useState({ L: 0.01, a: 0.01, b: 0.01 })
  const [result, setResult] = useState<any>(null)
  const [channel, setChannel] = useState<'L' | 'a' | 'b'>('b')
  const [error, setError] = useState('')
  const [loadingSeed, setLoadingSeed] = useState(false)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')

  useEffect(() => {
    if (!datasetId) return
    setLoadingSeed(true)
    const q = new URLSearchParams({ dataset_id: datasetId, limit: '500' })
    if (globalFilters.products[0]) q.set('product', globalFilters.products[0])
    if (globalFilters.thicknesses[0]) q.set('thickness', globalFilters.thicknesses[0])
    if (globalFilters.dateFrom) q.set('from_ts', globalFilters.dateFrom)
    if (globalFilters.dateTo) q.set('to_ts', globalFilters.dateTo)
    api.get(`/api/seed_rows?${q.toString()}`).then((r) => setSeedRows(r.data.rows || [])).catch(() => setSeedRows([])).finally(() => setLoadingSeed(false))
  }, [datasetId, globalFilters])

  useEffect(() => {
    if (!datasetId || !plateId || !modelTrained) return
    api.get(`/api/plate/${encodeURIComponent(plateId)}/baseline?dataset_id=${datasetId}`).then((r) => {
      setBaseline(r.data)
      setEditedKnobs(r.data.baseline_knobs || {})
      setResult(null)
    }).catch((e) => setError(e?.response?.data?.detail || 'Failed to load baseline'))
  }, [datasetId, plateId, modelTrained])

  const filteredSeedRows = useMemo(() => {
    return seedRows.filter((r) => `${r.plate} ${r.ts || ''} ${r.product || ''} ${r.thickness || ''}`.toLowerCase().includes(search.toLowerCase()))
  }, [seedRows, search])

  const knobRows = useMemo(() => {
    if (!baseline?.baseline_knobs) return []
    const active = new Set((baseline.active_cathodes || []).map((x: string) => x.toLowerCase()))
    const out: Array<{ cathode: string; knob: string; baseline: number; edited: number; delta: number; group: 'power' | 'main_gas' | 'segment_gas' | 'other'; active: boolean }> = []
    Object.entries(baseline.baseline_knobs as Record<string, number>).forEach(([knob, base]) => {
      const m = knob.match(KNOB_RE)
      const cath = m ? m[1].toLowerCase() : 'other'
      const suffix = (m ? m[2] : knob).toLowerCase()
      const group: any = suffix === 'pwr' ? 'power' : (suffix.startsWith('maingas') || /^m[123]g$/.test(suffix)) ? 'main_gas' : /^s\d+g$/.test(suffix) ? 'segment_gas' : 'other'
      if (group === 'other') return
      const edited = Number(editedKnobs[knob] ?? base ?? 0)
      const row = { cathode: cath, knob, baseline: Number(base ?? 0), edited, delta: edited - Number(base ?? 0), group, active: active.has(cath) }
      if (!activeOnly || row.active) out.push(row)
    })
    return out.sort((a, b) => a.cathode.localeCompare(b.cathode, undefined, { numeric: true }) || a.knob.localeCompare(b.knob, undefined, { numeric: true }))
  }, [baseline, editedKnobs, activeOnly])

  const grouped = useMemo(() => {
    const byGroup: Record<string, typeof knobRows> = { power: [], main_gas: [], segment_gas: [] }
    knobRows.forEach((r) => byGroup[r.group].push(r))
    return byGroup
  }, [knobRows])

  const runPredict = async () => {
    if (!datasetId || !plateId) return
    setLoading(true)
    setError('')
    try {
      const payload = {
        dataset_id: datasetId,
        plate_id: plateId,
        device,
        outputs,
        knob_overrides: editedKnobs,
        target: useTarget ? target : null,
        tolerance: useTarget ? tol : null,
        filter: {
          products: globalFilters.products,
          thicknesses: globalFilters.thicknesses,
          date_from: globalFilters.dateFrom || null,
          date_to: globalFilters.dateTo || null,
        },
      }
      const res = await runJob('/api/predict', payload, ({ progress, stage }) => { setProgress(progress); setStage(stage) })
      setResult(res)
    } catch (e: any) {
      setError(e.message || 'Prediction failed')
    } finally {
      setLoading(false)
    }
  }

  const resetCathode = (cathode: string) => {
    if (!baseline?.baseline_knobs) return
    const next = { ...editedKnobs }
    Object.entries(baseline.baseline_knobs as Record<string, number>).forEach(([k, v]) => {
      if (k.toLowerCase().startsWith(`${cathode.toLowerCase()}.`)) next[k] = Number(v ?? 0)
    })
    setEditedKnobs(next)
  }

  const resetAll = () => setEditedKnobs({ ...(baseline?.baseline_knobs || {}) })

  const applyDeltaToActive = (delta: number) => {
    if (!baseline?.baseline_knobs) return
    const active = new Set((baseline.active_cathodes || []).map((x: string) => x.toLowerCase()))
    const next = { ...editedKnobs }
    Object.entries(next).forEach(([k, v]) => {
      const m = k.match(KNOB_RE)
      if (m && active.has(m[1].toLowerCase())) next[k] = Number(v) + delta
    })
    setEditedKnobs(next)
  }

  const actualDevice = baseline?.actual_color?.[device] || {}
  const actualMean = result?.actual || {}
  const predBase = result?.pred_baseline || {}
  const predEdit = result?.pred_edited || {}

  const meanChart = useMemo(() => outputKeys(outputs).map((k) => ({ metric: k, actual: actualMean[k], pred_baseline: predBase[k], pred_edited: predEdit[k] })), [outputs, actualMean, predBase, predEdit])

  const profileChart = useMemo(() => {
    const pts = actualDevice?.[`${channel}_points`] || []
    const meanBase = predBase?.[channel]
    const meanEdit = predEdit?.[channel]
    if (!pts.length) return [{ p: 'mean', actual: actualDevice?.[`${channel}_mean`], pred_baseline: meanBase, pred_edited: meanEdit }]
    return pts.map((v: number, i: number) => ({ p: `p${i + 1}`, actual: v, pred_baseline: meanBase, pred_edited: meanEdit }))
  }, [actualDevice, channel, predBase, predEdit])

  const knobDeltaChart = useMemo(() => (result?.knob_changes || []).map((x: any) => ({ knob: x.knob, cathode: x.cathode, abs_delta: Math.abs(Number(x.delta || 0)) })).sort((a: any, b: any) => b.abs_delta - a.abs_delta).slice(0, 15), [result])

  const resultRows = useMemo(() => outputKeys(outputs).map((k) => ({ key: k, actual: actualMean[k], pred_baseline: predBase[k], pred_edited: predEdit[k], delta: (Number(predEdit[k] ?? 0) - Number(predBase[k] ?? 0)) })), [outputs, actualMean, predBase, predEdit])

  const exportPredictionJson = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'prediction_report.json'
    a.click()
  }

  const exportKnobCsv = () => {
    if (!result?.knob_changes) return
    const rows = [['cathode', 'knob', 'baseline', 'edited', 'delta']]
    result.knob_changes.forEach((r: any) => rows.push([r.cathode, r.knob, r.baseline, r.edited, r.delta]))
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([rows.map((r) => r.join(',')).join('\n')], { type: 'text/csv' }))
    a.download = 'knob_changes.csv'
    a.click()
  }

  if (!modelTrained) return <Alert variant='destructive'>Train a model first.</Alert>

  return <div className='space-y-6'>
    {!datasetId && <Alert variant='destructive'>Load data first.</Alert>}

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Step 1: Select baseline (Seed plate)</h3>
      <div className='grid md:grid-cols-3 gap-3'>
        <Input value={search} onChange={(e: any) => setSearch(e.target.value)} placeholder='Search plate | timestamp | product | thickness' />
        <Select value={plateId} onChange={(e: any) => setPlateId(e.target.value)}>
          <option value=''>Select seed plate</option>
          {filteredSeedRows.map((r) => <option key={r.plate} value={r.plate}>{r.plate} | {r.ts || '-'} | {r.product || '-'} | {r.thickness || '-'}</option>)}
        </Select>
        <div className='text-xs text-slate-500 flex items-center'>{loadingSeed ? 'Loading seed rows…' : `${filteredSeedRows.length} candidates`}</div>
      </div>
      {!plateId && <Alert>Select a seed plate to begin.</Alert>}
      {baseline && <Card className='p-3'>
        <p className='text-sm font-medium mb-1'>Baseline Summary</p>
        <div className='grid md:grid-cols-4 gap-2 text-sm'>
          <div>Product: {baseline.product || '—'}</div>
          <div>Thickness: {baseline.thickness || '—'}</div>
          <div>Timestamp: {baseline.ts || '—'}</div>
          <div>Active cathodes: {(baseline.active_cathodes || []).length}</div>
        </div>
        <Badge className='mt-2'>Baseline source: Actual row</Badge>
      </Card>}
    </Card>

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Step 2: What do you want to predict?</h3>
      <div className='flex gap-2'>
        {(['RG', 'RF', 'T'] as Device[]).map((d) => <Button key={d} variant={device === d ? 'default' : 'secondary'} onClick={() => setDevice(d)}>{d}</Button>)}
      </div>
      <div className='grid md:grid-cols-2 gap-3'>
        <div><label className='text-sm'>Output mode</label><Select value={outputs} onChange={(e: any) => setOutputs(e.target.value)}><option value='b_only'>b only</option><option value='lab'>L,a,b</option></Select></div>
        <div className='text-sm'>Current ACTUAL measured: {outputs === 'b_only' ? `b=${fmt(actualDevice?.b_mean)} (std ${fmt(actualDevice?.b_std)})` : `L=${fmt(actualDevice?.L_mean)}, a=${fmt(actualDevice?.a_mean)}, b=${fmt(actualDevice?.b_mean)}`}</div>
      </div>
      {!!(actualDevice?.b_points || []).length && <p className='text-xs text-slate-500'>Per-position points available (p1..p9).</p>}
    </Card>

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Step 3: Modify control knobs</h3>
      <div className='flex items-center justify-between text-sm'><span>Active cathodes only</span><Switch checked={activeOnly} onCheckedChange={(v: boolean) => setActiveOnly(v)} /></div>
      <div className='flex flex-wrap gap-2'>
        <Button variant='secondary' onClick={resetAll}><RotateCcw size={16} className='inline mr-1' />Reset all</Button>
        <Button variant='secondary' onClick={() => applyDeltaToActive(0.1)}>Apply +0.1 to all active</Button>
      </div>
      {(['power', 'main_gas', 'segment_gas'] as const).map((group) => (
        <Accordion key={group} title={`${group.replace('_', ' ')} (${grouped[group].length})`}>
          <div className='space-y-3'>
            {Object.entries(grouped[group].reduce((acc: any, r: any) => { (acc[r.cathode] ||= []).push(r); return acc }, {})).map(([cathode, rows]: any) => (
              <Card key={cathode} className='p-3'>
                <div className='flex items-center justify-between mb-2'>
                  <div className='flex items-center gap-2'><span className='font-medium'>{cathode}</span>{rows[0].active ? <Badge className='bg-emerald-100 text-emerald-700'>active</Badge> : <Badge>inactive</Badge>}</div>
                  <Button variant='secondary' onClick={() => resetCathode(cathode)}>Reset cathode</Button>
                </div>
                <div className='overflow-auto'>
                  <table className='min-w-full text-xs'>
                    <thead><tr className='border-b'><th className='text-left p-2'>Knob</th><th className='text-left p-2'>Baseline</th><th className='text-left p-2'>Editable</th><th className='text-left p-2'>Delta</th></tr></thead>
                    <tbody>
                      {rows.map((r: any) => <tr key={r.knob} className='border-b'><td className='p-2'>{r.knob}</td><td className='p-2'>{fmt(r.baseline)}</td><td className='p-2 w-36'><Input type='number' value={r.edited} onChange={(e: any) => setEditedKnobs({ ...editedKnobs, [r.knob]: Number(e.target.value) })} /></td><td className='p-2'>{fmt(r.delta)}</td></tr>)}
                    </tbody>
                  </table>
                </div>
              </Card>
            ))}
          </div>
        </Accordion>
      ))}
    </Card>

    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Target (optional)</h3>
      <div className='flex items-center justify-between text-sm'><span>Use target</span><Switch checked={useTarget} onCheckedChange={(v: boolean) => setUseTarget(v)} /></div>
      {useTarget && <div className='grid md:grid-cols-3 gap-2'>{outputKeys(outputs).map((k) => <div key={k}><label className='text-xs'>{k} target / tol</label><div className='flex gap-2'><Input type='number' value={(target as any)[k]} onChange={(e: any) => setTarget({ ...target, [k]: Number(e.target.value) })} /><Input type='number' value={(tol as any)[k]} onChange={(e: any) => setTol({ ...tol, [k]: Number(e.target.value) })} /></div></div>)}</div>}
    </Card>

    <Card className='space-y-3'>
      {loading && <><Progress value={progress} /><p className='text-sm text-slate-500'>{stage}</p></>}
      {error && <Alert variant='destructive'>{error}</Alert>}
      <Button onClick={runPredict} disabled={!datasetId || !plateId || loading}><Play size={16} className='inline mr-1' />Run prediction</Button>
    </Card>

    {loading && <div className='grid md:grid-cols-4 gap-3'>{[1, 2, 3, 4].map((i) => <Skeleton key={i} className='h-20' />)}</div>}

    {result && <>
      <div className='grid md:grid-cols-5 gap-3'>
        <Card><p className='text-xs text-slate-500'>Actual baseline b_mean</p><p className='text-2xl font-semibold'>{fmt(actualMean?.b)}</p></Card>
        <Card><p className='text-xs text-slate-500'>Pred baseline b_mean</p><p className='text-2xl font-semibold'>{fmt(predBase?.b)}</p></Card>
        <Card><p className='text-xs text-slate-500'>Pred edited b_mean</p><p className='text-2xl font-semibold'>{fmt(predEdit?.b)}</p></Card>
        <Card><p className='text-xs text-slate-500'>Improvement</p><p className='text-2xl font-semibold'>{fmt((Number(predEdit?.b || 0) - Number(predBase?.b || 0)))}</p></Card>
        <Card><p className='text-xs text-slate-500'>Loss edited</p><p className='text-2xl font-semibold'>{fmt(result.loss_edited)}</p>{useTarget && <Badge className={(result.loss_edited ?? 1) <= 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>{(result.loss_edited ?? 1) <= 0 ? 'Within tolerance' : 'Outside tolerance'}</Badge>}</Card>
      </div>

      <Card className='h-72'>
        <h3 className='text-sm font-medium mb-2'>Actual vs Predicted (mean)</h3>
        <ResponsiveContainer width='100%' height='90%'>
          <LineChart data={meanChart}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='metric' /><YAxis /><Tooltip /><Legend />
            <Line type='monotone' dataKey='actual' stroke='#2563eb' />
            <Line type='monotone' dataKey='pred_baseline' stroke='#b45309' />
            <Line type='monotone' dataKey='pred_edited' stroke='#16a34a' />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Card className='h-80'>
        <div className='flex gap-2 mb-2'>{(['L', 'a', 'b'] as const).map((k) => <Button key={k} variant={channel === k ? 'default' : 'secondary'} onClick={() => setChannel(k)}>{k}</Button>)}</div>
        <ResponsiveContainer width='100%' height='88%'>
          <LineChart data={profileChart}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='p' /><YAxis /><Tooltip /><Legend />
            <Line type='monotone' dataKey='actual' stroke='#2563eb' />
            <Line type='monotone' dataKey='pred_baseline' stroke='#b45309' strokeDasharray='4 4' />
            <Line type='monotone' dataKey='pred_edited' stroke='#16a34a' strokeDasharray='4 4' />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {!!knobDeltaChart.length && <Card className='h-72'>
        <h3 className='text-sm font-medium mb-2'>Top knob changes</h3>
        <ResponsiveContainer width='100%' height='90%'>
          <BarChart data={knobDeltaChart}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='knob' hide /><YAxis /><Tooltip /><Bar dataKey='abs_delta' fill='#2563eb' /></BarChart>
        </ResponsiveContainer>
      </Card>}

      <Card className='overflow-auto'>
        <h3 className='text-sm font-medium mb-2'>Results table</h3>
        <table className='min-w-full text-sm'>
          <thead><tr className='border-b'><th className='text-left p-2'>Output</th><th className='text-left p-2'>Actual</th><th className='text-left p-2'>Pred baseline</th><th className='text-left p-2'>Pred edited</th><th className='text-left p-2'>Delta</th></tr></thead>
          <tbody>{resultRows.map((r) => <tr key={r.key} className='border-b'><td className='p-2'>{r.key}</td><td className='p-2'>{fmt(r.actual)}</td><td className='p-2'>{fmt(r.pred_baseline)}</td><td className='p-2'>{fmt(r.pred_edited)}</td><td className='p-2'>{fmt(r.delta)}</td></tr>)}</tbody>
        </table>
      </Card>

      <div className='flex gap-2'>
        <Button variant='secondary' onClick={exportPredictionJson}><Download size={16} className='inline mr-1' />Export prediction JSON</Button>
        <Button variant='secondary' onClick={exportKnobCsv}><Download size={16} className='inline mr-1' />Export knob changes CSV</Button>
      </div>
    </>}
  </div>
}
