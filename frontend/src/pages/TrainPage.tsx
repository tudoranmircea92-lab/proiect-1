import { Download, Play } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, Input, Select, Switch, Button, Progress, Skeleton, Alert } from '../components/ui'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'
import { runJob } from '../lib/jobs'

export function TrainPage() {
  const { datasetId, setModelTrained } = useDataset()
  const [models, setModels] = useState<string[]>([])
  const [modelType, setModelType] = useState('hist_gradient_boosting')
  const [split, setSplit] = useState<'time'|'random'>('time')
  const [ratio, setRatio] = useState(0.8)
  const [seed, setSeed] = useState(42)
  const [toggles, setToggles] = useState({ include_power:true, include_main_gas:true, include_main_gas_alt:true, include_segment_gas:true, include_context_numeric:true, include_context_categorical:true, include_context_keyword_allowlist:true })
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')

  useEffect(() => { api.get('/api/models').then(r => setModels(r.data.models)) }, [])

  const train = async () => {
    if (!datasetId) { setError('Load data first'); return }
    setLoading(true); setError('')
    try {
      const res = await runJob('/api/train', { dataset_id: datasetId, config: { model_type: modelType, split: { method: split, ratio, random_seed: seed }, features: toggles } }, ({progress, stage})=>{setProgress(progress); setStage(stage)})
      setResult(res)
      setModelTrained(true)
    } catch (e:any) { setError(e.message || 'Train failed') } finally { setLoading(false) }
  }

  const fmt = (v: any) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(4))
  const targetRows = useMemo(()=> result ? Object.entries(result.metrics_per_target).map(([k,v]:any)=>({target:k, mae:v.mae, rmse:v.rmse})) : [], [result])
  const grouped = useMemo(()=>{
    const d: any = { RG_mean:[], RG_std:[], RF_mean:[], RF_std:[], T_mean:[], T_std:[] }
    targetRows.forEach((r:any)=>{ const p=r.target.split('_'); d[`${p[1]}_${p[2]}`].push(r.mae) })
    return Object.entries(d).map(([k,v]:any)=>({ group:k, mae:v.length? v.reduce((a:number,b:number)=>a+b,0)/v.length:0 }))
  }, [targetRows])

  return <div className='space-y-6'>
    {!datasetId && <Alert variant='destructive'>Load data first.</Alert>}

    <div className='grid md:grid-cols-2 gap-6'>
      <Card className='space-y-3'>
        <h3 className='text-sm font-medium tracking-tight'>Model</h3>
        <div className='grid gap-3'>
          <div><label className='text-sm'>Model type</label><Select value={modelType} onChange={(e:any)=>setModelType(e.target.value)}>{models.map(m=><option key={m}>{m}</option>)}</Select></div>
          <div><label className='text-sm'>Split</label><Select value={split} onChange={(e:any)=>setSplit(e.target.value)}><option value='time'>time</option><option value='random'>random</option></Select></div>
          <div><label className='text-sm'>Split ratio: {ratio.toFixed(2)}</label><Input type='range' min='0.5' max='0.95' step='0.01' value={ratio} onChange={(e:any)=>setRatio(Number(e.target.value))}/></div>
          <div><label className='text-sm'>Random seed</label><Input type='number' value={seed} onChange={(e:any)=>setSeed(Number(e.target.value))}/></div>
        </div>
      </Card>

      <Card className='space-y-3'>
        <h3 className='text-sm font-medium tracking-tight'>Features</h3>
        {Object.entries(toggles).map(([k,v])=>
          <div key={k} className='flex items-center justify-between text-sm'><span>{k}</span><Switch checked={v as boolean} onCheckedChange={(nv:boolean)=>setToggles({...toggles,[k]:nv})}/></div>
        )}
      </Card>
    </div>

    <Card className='space-y-3'>
      {loading && <><Progress value={progress}/><p className='text-sm text-slate-500'>{stage}</p></>}
      {error && <Alert variant='destructive'>{error}</Alert>}
      <Button onClick={train} disabled={!datasetId || loading}><Play size={16} className='inline mr-1'/>Train model</Button>
    </Card>

    {loading && <div className='grid md:grid-cols-3 gap-3'>{[1,2,3].map(i=><Skeleton key={i} className='h-24' />)}</div>}

    {result && <>
      <div className='grid md:grid-cols-3 gap-3'>
        <Card><p className='text-sm font-medium'>mean MAE (means)</p><p className='text-2xl font-semibold'>{fmt(result.aggregate_metrics.mean_mae_means)}</p></Card>
        <Card><p className='text-sm font-medium'>mean MAE (stds)</p><p className='text-2xl font-semibold'>{fmt(result.aggregate_metrics.mean_mae_stds)}</p></Card>
        <Card><p className='text-sm font-medium'>overall score</p><p className='text-2xl font-semibold'>{fmt((result.aggregate_metrics.mean_mae_means ?? 0) + (result.aggregate_metrics.mean_mae_stds ?? 0))}</p></Card>
      </div>

      <Card className='h-72'>
        <ResponsiveContainer width='100%' height='100%'>
          <BarChart data={grouped}><CartesianGrid strokeDasharray='3 3'/><XAxis dataKey='group'/><YAxis/><Tooltip/><Bar dataKey='mae' fill='#2563eb'/></BarChart>
        </ResponsiveContainer>
      </Card>

      <Card className='overflow-auto'>
        <table className='min-w-full text-sm'><thead><tr className='border-b'><th className='text-left p-2'>Target</th><th className='text-left p-2'>MAE</th><th className='text-left p-2'>RMSE</th></tr></thead><tbody>{targetRows.map((r:any)=><tr key={r.target} className='border-b'><td className='p-2'>{r.target}</td><td className='p-2'>{fmt(r.mae)}</td><td className='p-2'>{fmt(r.rmse)}</td></tr>)}</tbody></table>
      </Card>

      <Card><Button variant='secondary' onClick={()=>window.open(`http://localhost:8000/api/artifacts/${result.artifact_id}/download`)}><Download size={16} className='inline mr-1'/>Download artifacts</Button></Card>
    </>}
  </div>
}
