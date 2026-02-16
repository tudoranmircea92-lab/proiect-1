import { Play } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Input, Progress, Select } from '../components/ui'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'
import { runJob } from '../lib/jobs'

const empty = { L: 0, a: 0, b: 0 }

export function OptimizePage() {
  const { datasetId } = useDataset()
  const [seedRows, setSeedRows] = useState<any[]>([])
  const [seedIdx, setSeedIdx] = useState<number | null>(null)
  const [method, setMethod] = useState<'nn'|'search'>('nn')
  const [targets, setTargets] = useState({ RG: {...empty}, RF: {...empty}, T: {...empty} })
  const [sol, setSol] = useState<any[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')

  useEffect(() => { if (datasetId) api.get(`/api/data/seed-plates?dataset_id=${datasetId}`).then(r => setSeedRows(r.data.rows || [])) }, [datasetId])
  const seed = useMemo(() => (seedIdx === null ? null : seedRows[seedIdx]), [seedIdx, seedRows])

  const run = async () => {
    if (!datasetId) { setError('Load data first'); return }
    if (!seed) { setError('Select a seed row'); return }
    setLoading(true); setError('')
    try {
      const result = await runJob('/api/optimize', { dataset_id: datasetId, method, targets, constraints: {RG:empty,RF:empty,T:empty}, bounds: {pwr_pct:5, gas_pct:5}, params: {k_neighbors:5,n_iterations:300,n_solutions:5,device_weights:{RG:1,RF:1,T:1}}, seed_plate: seed.meta?.plate, seed_control_knobs: seed.control_knobs, seed_context: seed.context }, ({progress, stage})=>{setProgress(progress); setStage(stage)})
      setSol(result.solutions)
    } catch (e:any) { setError(e.message) } finally { setLoading(false) }
  }

  return <div className='space-y-6'>
    {!datasetId && <Alert variant='destructive'>Load data first.</Alert>}
    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Optimize</h3>
      <Select value={seedIdx ?? ''} onChange={(e:any)=>setSeedIdx(e.target.value === '' ? null : Number(e.target.value))}><option value=''>Select seed row</option>{seedRows.map((r,i)=><option key={i} value={i}>{r.meta?.plate ?? `row-${i}`}</option>)}</Select>
      <Select value={method} onChange={(e:any)=>setMethod(e.target.value)}><option value='nn'>Nearest neighbor</option><option value='search'>Local search</option></Select>
      <div className='grid md:grid-cols-3 gap-2'>{(['RG','RF','T'] as const).map(dev=><div key={dev} className='space-y-1'>{(['L','a','b'] as const).map(ch=><Input key={ch} type='number' value={(targets as any)[dev][ch]} onChange={(e:any)=>setTargets({...targets, [dev]: {...(targets as any)[dev], [ch]: Number(e.target.value)}})} placeholder={`${dev} ${ch}`}/>)}</div>)}</div>
      {loading && <><Progress value={progress}/><p className='text-sm text-slate-500'>{stage}</p></>}
      {error && <Alert variant='destructive'>{error}</Alert>}
      <Button onClick={run} disabled={!datasetId || loading}><Play size={16} className='inline mr-1'/>Run optimization</Button>
    </Card>

    {sol.length>0 && <Card className='overflow-auto'><table className='min-w-full text-sm'><thead><tr className='border-b'><th className='p-2 text-left'>Rank</th><th className='p-2 text-left'>Loss</th></tr></thead><tbody>{sol.map((s,i)=><tr key={i} className='border-b'><td className='p-2'>{s.rank}</td><td className='p-2'>{Number(s.loss).toFixed(4)}</td></tr>)}</tbody></table></Card>}
  </div>
}
