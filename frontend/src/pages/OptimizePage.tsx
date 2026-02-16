import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'

const empty = { L: 0, a: 0, b: 0 }

export function OptimizePage() {
  const [seedRows, setSeedRows] = useState<any[]>([])
  const [seedIdx, setSeedIdx] = useState<number | null>(null)
  const [method, setMethod] = useState<'nn'|'search'>('nn')
  const [targets, setTargets] = useState({ RG: {...empty}, RF: {...empty}, T: {...empty} })
  const [stdMax, setStdMax] = useState({ RG: { ...empty }, RF: { ...empty }, T: { ...empty } })
  const [k, setK] = useState(5)
  const [iters, setIters] = useState(300)
  const [nSol, setNSol] = useState(5)
  const [pwrPct, setPwrPct] = useState(5)
  const [gasPct, setGasPct] = useState(5)
  const [sol, setSol] = useState<any[]>([])
  const [error, setError] = useState('')
  const { datasetId } = useDataset()

  useEffect(() => { if (datasetId) api.get(`/api/data/seed-plates?dataset_id=${datasetId}`).then(r => setSeedRows(r.data.rows || [])) }, [datasetId])
  const seed = useMemo(() => (seedIdx === null ? null : seedRows[seedIdx]), [seedIdx, seedRows])

  const run = async () => {
    if (!seed) {
      setError('Seed row is required to freeze context for optimization.')
      return
    }
    setError('')
    try {
      if (!datasetId) { setError('Load data first'); return }
      const payload = {
        dataset_id: datasetId,
        method,
        targets,
        constraints: stdMax,
        bounds: { pwr_pct: pwrPct, gas_pct: gasPct },
        params: { k_neighbors: k, n_iterations: iters, n_solutions: nSol, device_weights: { RG: 1, RF: 1, T: 1 } },
        seed_plate: seed.meta?.plate,
        seed_control_knobs: seed.control_knobs,
        seed_context: seed.context,
      }
      const res = await api.post('/api/optimize', payload)
      setSol(res.data.solutions)
    } catch (e:any) {
      setError(e?.response?.data?.detail ?? 'Optimization failed')
    }
  }

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(sol, null, 2)], { type: 'application/json' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'solutions.json'; a.click()
  }

  return <div className='space-y-4'>
    {!datasetId && <section className='card text-slate-600'>Load data first from the Data tab.</section>}
    <section className='card space-y-3'>
      <h2 className='text-lg font-semibold'>Optimize</h2>
      <select className='input' value={seedIdx ?? ''} onChange={e=>setSeedIdx(e.target.value === '' ? null : Number(e.target.value))}>
        <option value=''>Select seed row (required)</option>
        {seedRows.map((r, i)=><option key={i} value={i}>{r.meta?.plate ?? `row-${i}`}</option>)}
      </select>
      <p className='text-xs text-slate-600'>🔒 Context is locked/frozen and used for prediction only. Optimizer changes control knobs only.</p>
    </section>

    <section className='card space-y-3'>
      <div className='grid md:grid-cols-3 gap-3'>
        {(['RG','RF','T'] as const).map(dev => <div key={dev} className='border p-3 rounded-lg space-y-2'>
          <p className='font-medium'>{dev} Mean Targets</p>
          {(['L','a','b'] as const).map(ch => <input key={ch} className='input' type='number' value={(targets as any)[dev][ch]} onChange={e=>setTargets({...targets, [dev]: {...(targets as any)[dev], [ch]: Number(e.target.value)}})} placeholder={`${ch} mean`}/>)}
        </div>)}
      </div>
      <div className='grid md:grid-cols-5 gap-2'>
        <select className='input' value={method} onChange={e=>setMethod(e.target.value as any)}><option value='nn'>Nearest Neighbor</option><option value='search'>Local Search</option></select>
        <input className='input' type='number' value={k} onChange={e=>setK(Number(e.target.value))} placeholder='K'/>
        <input className='input' type='number' value={iters} onChange={e=>setIters(Number(e.target.value))} placeholder='Iterations'/>
        <input className='input' type='number' value={pwrPct} onChange={e=>setPwrPct(Number(e.target.value))} placeholder='±% pwr'/>
        <input className='input' type='number' value={gasPct} onChange={e=>setGasPct(Number(e.target.value))} placeholder='±% gas'/>
      </div>
      <button className='btn' onClick={run} disabled={!datasetId}>Generate Solutions</button>
      {error && <p className='text-red-600 text-sm'>{error}</p>}
    </section>

    {sol.length > 0 && <section className='card space-y-3'>
      <div className='flex justify-between'><h3 className='font-semibold'>Candidates</h3><button className='btn-secondary' onClick={exportJson}>Export JSON</button></div>
      <div className='space-y-3'>{sol.map((s, i)=><div key={i} className='border rounded-lg p-3'><p className='font-medium'>#{s.rank} loss={s.loss.toFixed(4)}</p><pre className='text-xs'>{JSON.stringify(s, null, 2)}</pre></div>)}</div>
    </section>}
  </div>
}
