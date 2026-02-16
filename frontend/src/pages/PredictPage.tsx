import { Play } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Alert, Button, Card, Input, Progress } from '../components/ui'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'
import { runJob } from '../lib/jobs'

export function PredictPage() {
  const [seedRows, setSeedRows] = useState<any[]>([])
  const [controlKnobs, setControlKnobs] = useState<Record<string, number>>({})
  const [context, setContext] = useState<Record<string, any>>({})
  const [pred, setPred] = useState<Record<string, number> | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')
  const { datasetId } = useDataset()

  useEffect(() => { if (datasetId) api.get(`/api/data/seed-plates?dataset_id=${datasetId}`).then(r => setSeedRows(r.data.rows || [])) }, [datasetId])

  const runPredict = async () => {
    if (!datasetId) { setError('Load data first'); return }
    setLoading(true); setError('')
    try {
      const res = await runJob('/api/predict', { dataset_id: datasetId, control_knobs: controlKnobs, context }, ({progress, stage})=>{setProgress(progress); setStage(stage)})
      setPred(res.predictions)
    } catch (e:any) { setError(e.message) } finally { setLoading(false) }
  }

  return <div className='space-y-6'>
    {!datasetId && <Alert variant='destructive'>Load data first.</Alert>}
    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Seed plate</h3>
      <select className='w-full border rounded-md p-2 text-sm' onChange={e=>{const row=seedRows[Number(e.target.value)]; if(row){setControlKnobs(row.control_knobs||{}); setContext(row.context||{})}}}>
        <option>Select seed row</option>
        {seedRows.map((r, i)=><option key={i} value={i}>{r.meta?.plate ?? `row-${i}`}</option>)}
      </select>
      {loading && <><Progress value={progress}/><p className='text-sm text-slate-500'>{stage}</p></>}
      {error && <Alert variant='destructive'>{error}</Alert>}
      <Button onClick={runPredict} disabled={!datasetId || loading}><Play size={16} className='inline mr-1'/>Run prediction</Button>
    </Card>

    <Card>
      <h3 className='text-sm font-medium tracking-tight mb-2'>Editable control knobs</h3>
      <div className='grid md:grid-cols-4 gap-2'>
        {Object.keys(controlKnobs).slice(0, 80).map(k => <label key={k} className='text-xs'>{k}<Input type='number' value={controlKnobs[k]} onChange={(e:any)=>setControlKnobs({...controlKnobs,[k]:Number(e.target.value)})}/></label>)}
      </div>
    </Card>

    {pred && <Card className='overflow-auto'><table className='min-w-full text-sm'><thead><tr className='border-b'><th className='text-left p-2'>Target</th><th className='text-left p-2'>Pred</th></tr></thead><tbody>{Object.entries(pred).map(([k,v])=><tr key={k} className='border-b'><td className='p-2'>{k}</td><td className='p-2'>{Number(v).toFixed(4)}</td></tr>)}</tbody></table></Card>}
  </div>
}
