import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'

export function TrainPage() {
  const [models, setModels] = useState<string[]>([])
  const [modelType, setModelType] = useState('hist_gradient_boosting')
  const [split, setSplit] = useState<'time'|'random'>('time')
  const [ratio, setRatio] = useState(0.8)
  const [seed, setSeed] = useState(42)
  const [toggles, setToggles] = useState({
    include_power: true,
    include_main_gas: true,
    include_main_gas_alt: true,
    include_segment_gas: true,
    include_context_numeric: true,
    include_context_categorical: true,
    include_context_keyword_allowlist: true,
  })
  const [result, setResult] = useState<any>(null)
  const [toast, setToast] = useState('')
  const { datasetId } = useDataset()
  const [error, setError] = useState('')

  useEffect(() => { api.get('/api/models').then(r => setModels(r.data.models)) }, [])

  const train = async () => {
    if (!datasetId) { setError('Load data first'); return }
    setError(''); setToast('')
    try {
      const res = await api.post('/api/train', { dataset_id: datasetId, config: { model_type: modelType, split: { method: split, ratio, random_seed: seed }, features: toggles } })
      setResult(res.data); setToast('Training completed successfully')
    } catch (e:any) {
      setError(e?.response?.data?.detail ?? 'Train failed')
    }
  }

  const chartData = result ? Object.entries(result.metrics_per_target).map(([t, m]: any) => ({ target: t, mae: m.mae })) : []

  return <div className='space-y-4'>
    {!datasetId && <section className='card text-slate-600'>Load data first from the Data tab.</section>}
    <section className='card space-y-3'>
      <h2 className='text-lg font-semibold'>Train</h2>
      <div className='grid md:grid-cols-4 gap-3'>
        <select className='input' value={modelType} onChange={e=>setModelType(e.target.value)}>{models.map(m=><option key={m}>{m}</option>)}</select>
        <select className='input' value={split} onChange={e=>setSplit(e.target.value as any)}><option value='time'>Time split</option><option value='random'>Random split</option></select>
        <input className='input' type='number' step='0.05' min='0.5' max='0.95' value={ratio} onChange={e=>setRatio(Number(e.target.value))}/>
        <input className='input' type='number' value={seed} onChange={e=>setSeed(Number(e.target.value))}/>
      </div>
      <div className='grid md:grid-cols-4 gap-2 text-sm'>
        {Object.entries(toggles).map(([k,v])=><label key={k} className='flex gap-2 items-center'><input type='checkbox' checked={v} onChange={e=>setToggles({...toggles,[k]:e.target.checked})}/>{k}</label>)}
      </div>
      <button className='btn' onClick={train} disabled={!datasetId}>Train Model</button>
      {toast && <p className='text-emerald-600 text-sm'>{toast}</p>}
      {error && <p className='text-red-600 text-sm'>{error}</p>}
    </section>

    {result && <>
      <section className='card grid md:grid-cols-4 gap-3'>
        <div><p className='label'>Mean MAE (means)</p><p className='text-xl font-semibold'>{result.aggregate_metrics.mean_mae_means.toFixed(4)}</p></div>
        <div><p className='label'>Mean MAE (stds)</p><p className='text-xl font-semibold'>{result.aggregate_metrics.mean_mae_stds.toFixed(4)}</p></div>
        <div><p className='label'>Dropped rows (missing Y)</p><p className='text-xl font-semibold'>{result.dropped_rows_missing_targets}</p></div>
        <div><p className='label'>Total features</p><p className='text-xl font-semibold'>{result.selected_feature_counts.total}</p></div>
      </section>
      <section className='card'>
        <p className='text-sm'>Controls: {result.feature_schema.control_knobs.length} | Context numeric: {result.feature_schema.context_numeric.length} | Context categorical: {result.feature_schema.context_categorical.length}</p>
        <p className='text-xs text-slate-600 mt-1'>Keyword forced: {(result.feature_schema.keyword_forced_context || []).join(', ') || 'None'}</p>
      </section>
      <section className='card h-80'>
        <ResponsiveContainer width='100%' height='100%'>
          <BarChart data={chartData}><CartesianGrid strokeDasharray='3 3' /><XAxis dataKey='target' interval={0} angle={-45} textAnchor='end' height={100}/><YAxis/><Tooltip/><Bar dataKey='mae' fill='#2563eb'/></BarChart>
        </ResponsiveContainer>
      </section>
      <section className='card'>
        <a className='btn-secondary' href={`http://localhost:8000/api/artifacts/${result.artifact_id}/download`}>Download Artifacts</a>
      </section>
    </>}
  </div>
}
