import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export function PredictPage() {
  const [seedRows, setSeedRows] = useState<any[]>([])
  const [controlKnobs, setControlKnobs] = useState<Record<string, number>>({})
  const [context, setContext] = useState<Record<string, any>>({})
  const [pred, setPred] = useState<Record<string, number> | null>(null)
  const [error, setError] = useState('')

  useEffect(() => { api.get('/api/data/seed-plates').then(r => setSeedRows(r.data.rows || [])) }, [])

  const applySeed = (idx: number) => {
    const row = seedRows[idx]
    if (!row) return
    setControlKnobs(row.control_knobs || {})
    setContext(row.context || {})
  }

  const runPredict = async () => {
    setError('')
    try {
      const res = await api.post('/api/predict', { control_knobs: controlKnobs, context })
      setPred(res.data.predictions)
    } catch (e:any) {
      setError(e?.response?.data?.detail ?? 'Prediction failed')
    }
  }

  return <div className='space-y-4'>
    <section className='card space-y-3'>
      <h2 className='text-lg font-semibold'>Predict</h2>
      <select className='input' onChange={e=>applySeed(Number(e.target.value))}>
        <option>Select seed row</option>
        {seedRows.map((r, i)=><option key={i} value={i}>{r.meta?.plate ?? `row-${i}`}</option>)}
      </select>
      <p className='text-xs text-slate-600'>🔒 Context is read-only: used for prediction, not optimized.</p>
    </section>

    <section className='card'>
      <h3 className='font-semibold mb-2'>Editable control knobs</h3>
      <div className='grid md:grid-cols-4 gap-2'>
        {Object.keys(controlKnobs).slice(0, 120).map(k => (
          <label key={k} className='text-xs'>{k}<input className='input' type='number' value={controlKnobs[k]} onChange={e=>setControlKnobs({...controlKnobs,[k]:Number(e.target.value)})}/></label>
        ))}
      </div>
    </section>

    <section className='card'>
      <h3 className='font-semibold mb-2'>🔒 Context (read-only)</h3>
      <div className='grid md:grid-cols-3 gap-2'>
        {Object.entries(context).slice(0, 120).map(([k,v]) => (
          <label key={k} className='text-xs'>{k}<input className='input bg-slate-100' readOnly value={String(v ?? '')}/></label>
        ))}
      </div>
      <button className='btn mt-3' onClick={runPredict}>Predict 18 Outputs</button>
      {error && <p className='text-red-600 text-sm mt-2'>{error}</p>}
    </section>

    {pred && <section className='card'><pre className='text-sm'>{JSON.stringify(pred, null, 2)}</pre></section>}
  </div>
}
