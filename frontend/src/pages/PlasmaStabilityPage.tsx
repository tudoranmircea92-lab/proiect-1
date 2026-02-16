import { Download, Play } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Alert, Button, Card, Input, Progress, Select } from '../components/ui'
import { useDataset } from '../lib/datasetContext'
import { runJob } from '../lib/jobs'

export function PlasmaStabilityPage() {
  const { datasetId } = useDataset()
  const [dateFrom, setDateFrom] = useState('2024-01-01')
  const [dateTo, setDateTo] = useState('2024-12-31')
  const [threshold, setThreshold] = useState(0)
  const [agg, setAgg] = useState<'mean'|'median'>('mean')
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')

  const run = async () => {
    if (!datasetId) { setError('Load data first'); return }
    setLoading(true); setError('')
    try {
      const res = await runJob('/api/plasma_stability', { dataset_id: datasetId, mode:'auto', date_from: dateFrom, date_to: dateTo, active_threshold: threshold, agg }, ({progress, stage})=>{setProgress(progress); setStage(stage)})
      setResult(res)
    } catch (e:any) { setError(e.message) } finally { setLoading(false) }
  }

  const chartData = useMemo(()=> result?.per_cathode ?? [], [result])
  const firstSeries = useMemo(()=> {
    const keys = Object.keys(result?.timeseries ?? {})
    return keys.length ? result.timeseries[keys[0]] : []
  }, [result])

  return <div className='space-y-6'>
    {!datasetId && <Alert variant='destructive'>Load data first.</Alert>}
    <Card className='space-y-3'>
      <h3 className='text-sm font-medium tracking-tight'>Plasma Stability</h3>
      <div className='grid md:grid-cols-5 gap-2'>
        <Input type='date' value={dateFrom} onChange={(e:any)=>setDateFrom(e.target.value)} />
        <Input type='date' value={dateTo} onChange={(e:any)=>setDateTo(e.target.value)} />
        <Select value={String(threshold)} onChange={(e:any)=>setThreshold(Number(e.target.value))}><option value='0'>0</option><option value='0.1'>0.1</option><option value='1'>1.0</option></Select>
        <Select value={agg} onChange={(e:any)=>setAgg(e.target.value)}><option value='mean'>mean</option><option value='median'>median</option></Select>
        <Button onClick={run} disabled={!datasetId || loading}><Play size={16} className='inline mr-1'/>Run</Button>
      </div>
      {loading && <><Progress value={progress}/><p className='text-sm text-slate-500'>{stage}</p></>}
      {error && <Alert variant='destructive'>{error}</Alert>}
    </Card>

    {result && <>
      <div className='grid md:grid-cols-4 gap-3'>
        <Card><p className='text-sm font-medium'>Overall score</p><p className='text-2xl font-semibold'>{Number(result.summary.overall_stability_score ?? 0).toFixed(4)}</p></Card>
        <Card><p className='text-sm font-medium'>Vacuum CV</p><p className='text-2xl font-semibold'>{Number(result.summary.vacuum_cv ?? 0).toFixed(4)}</p></Card>
        <Card><p className='text-sm font-medium'>Uniformity current</p><p className='text-2xl font-semibold'>{Number(result.summary.uniformity_cv_current ?? 0).toFixed(4)}</p></Card>
        <Card><p className='text-sm font-medium'>Uniformity power</p><p className='text-2xl font-semibold'>{Number(result.summary.uniformity_cv_power ?? 0).toFixed(4)}</p></Card>
      </div>

      <Card className='h-72'><ResponsiveContainer width='100%' height='100%'><BarChart data={chartData}><CartesianGrid strokeDasharray='3 3'/><XAxis dataKey='cathode_id'/><YAxis/><Tooltip/><Bar dataKey='cv_power' fill='#2563eb'/></BarChart></ResponsiveContainer></Card>
      <Card className='h-72'><ResponsiveContainer width='100%' height='100%'><LineChart data={firstSeries}><CartesianGrid strokeDasharray='3 3'/><XAxis dataKey='ts'/><YAxis/><Tooltip/><Line type='monotone' dataKey='cv_power' dot={false} stroke='#2563eb'/></LineChart></ResponsiveContainer></Card>
      <Card className='overflow-auto'><table className='min-w-full text-sm'><thead><tr className='border-b'><th className='p-2 text-left'>Cathode</th><th className='p-2 text-left'>CV power</th><th className='p-2 text-left'>CV current</th></tr></thead><tbody>{chartData.map((r:any)=><tr key={r.cathode_id} className='border-b'><td className='p-2'>{r.cathode_id}</td><td className='p-2'>{Number(r.cv_power).toFixed(4)}</td><td className='p-2'>{Number(r.cv_current).toFixed(4)}</td></tr>)}</tbody></table></Card>
      <Card><Button variant='secondary' onClick={()=>window.open('http://localhost:8000/api/plasma_stability/export?format=csv')}><Download size={16} className='inline mr-1'/>Export</Button></Card>
    </>}
  </div>
}
