import { Upload, FolderOpen } from 'lucide-react'
import { useRef, useState } from 'react'
import { runJob, runUploadJob } from '../lib/jobs'
import { useDataset } from '../lib/datasetContext'
import { Accordion, Alert, Badge, Button, Card, Input, Progress, Select, Skeleton } from '../components/ui'

type LoadResp = {
  dataset_id: string
  saved_path?: string
  rows: number
  columns: number
  preview: Record<string, unknown>[]
  grouped_columns: Record<string, string[]>
  debug?: any
}

export function DataPage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [path, setPath] = useState('')
  const [format, setFormat] = useState<'auto' | 'csv' | 'parquet'>('auto')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [data, setData] = useState<LoadResp | null>(null)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')
  const { setDatasetId, setDatasetPath, setDatasetSummary, setDatasetName, setGroupedColumns, setModelTrained } = useDataset()

  const onDone = (profile: LoadResp) => {
    setData(profile)
    setDatasetId(profile.dataset_id)
    setDatasetPath(profile.saved_path || '')
    setDatasetSummary({ rows: profile.rows, columns: profile.columns })
    setDatasetName((profile.saved_path || selectedFile?.name || path || "dataset").split(/[\\/]/).pop() || "dataset")
    setGroupedColumns(profile.grouped_columns || null)
    setModelTrained(false)
    setToast(`Loaded ${profile.rows} rows, ${profile.columns} columns. Detected knobs: pwr=${profile.grouped_columns.power?.length ?? 0}, mainGas=${profile.grouped_columns.main_gas?.length ?? 0}, segmentGas=${profile.grouped_columns.segment_gas?.length ?? 0}`)
  }

  const uploadProfile = async () => {
    if (!selectedFile) return
    setLoading(true); setError(''); setToast('')
    try {
      const form = new FormData()
      form.append('file', selectedFile)
      form.append('format', format)
      const result = await runUploadJob(form, ({progress, stage})=>{setProgress(progress); setStage(stage)})
      onDone(result.profile)
    } catch (e: any) {
      setError(e.message || 'Upload failed')
    } finally { setLoading(false) }
  }

  const loadFromPath = async () => {
    setLoading(true); setError(''); setToast('')
    try {
      const result = await runJob('/api/data/load', { path, format }, ({progress, stage})=>{setProgress(progress); setStage(stage)})
      onDone(result)
    } catch (e:any) {
      setError(e.message || 'Load failed')
    } finally { setLoading(false) }
  }

  const groups = data?.grouped_columns ?? {}
  const previewColumns = data?.preview?.length ? Object.keys(data.preview[0]) : []
  const knobsZero = !!data && (groups.control_knobs?.length ?? 0) === 0

  return <div className='space-y-6'>
    <Card className='space-y-4'>
      <div>
        <h2 className='text-sm font-medium tracking-tight'>Upload + Profile</h2>
        <p className='text-sm text-slate-500'>Select a parquet/csv file and profile it.</p>
      </div>

      {loading && <div className='space-y-2'><Progress value={progress} /><p className='text-sm text-slate-500'>{stage}</p></div>}
      {toast && <Alert>{toast}</Alert>}
      {error && <Alert variant='destructive'>{error}</Alert>}

      <div className='grid md:grid-cols-4 gap-3 items-end'>
        <div className='md:col-span-2 space-y-1'>
          <label className='text-sm font-medium'>Selected file</label>
          <div className='border rounded-md p-2 text-sm'>{selectedFile ? `${selectedFile.name} • ${Math.round(selectedFile.size/1024)} KB • ${selectedFile.type || 'n/a'}` : 'No file selected'}</div>
        </div>
        <div><label className='text-sm font-medium'>Format</label><Select value={format} onChange={(e:any)=>setFormat(e.target.value)}><option value='auto'>Auto</option><option value='parquet'>Parquet</option><option value='csv'>CSV</option></Select></div>
        <div className='flex gap-2'>
          <input ref={fileRef} type='file' className='hidden' accept='.parquet,.csv' onChange={(e)=>setSelectedFile(e.target.files?.[0] ?? null)} />
          <Button variant='secondary' onClick={()=>fileRef.current?.click()}><FolderOpen size={16} className='inline mr-1'/>Browse...</Button>
          <Button onClick={uploadProfile} disabled={!selectedFile || loading}><Upload size={16} className='inline mr-1'/>Upload & Profile</Button>
        </div>
      </div>

      <Accordion title='Advanced: Load from server path'>
        <div className='grid md:grid-cols-4 gap-3'>
          <div className='md:col-span-3'><Input value={path} onChange={(e:any)=>setPath(e.target.value)} placeholder='C:\\data\\glass.parquet' /></div>
          <Button onClick={loadFromPath} disabled={!path || loading}>Load & Profile</Button>
        </div>
      </Accordion>
    </Card>

    {loading && !data && <div className='grid md:grid-cols-4 gap-3'>{[1,2,3,4].map(i=><Skeleton key={i} className='h-20'/>)}</div>}

    {data && <>
      <Card className='space-y-3'>
        <div className='flex items-center justify-between'><h3 className='text-sm font-medium tracking-tight'>Dataset Summary</h3><p className='text-sm text-slate-500'>Rows {data.rows} • Cols {data.columns}</p></div>
        <div className='grid md:grid-cols-4 gap-3'>
          <Card className='p-3'><p className='text-sm font-medium'>Targets</p><p>{groups.targets?.length ?? 0}</p></Card>
          <Card className='p-3'><p className='text-sm font-medium'>Control knobs</p><p>{groups.control_knobs?.length ?? 0}</p></Card>
          <Card className='p-3'><p className='text-sm font-medium'>Context numeric</p><p>{groups.context_numeric?.length ?? 0}</p></Card>
          <Card className='p-3'><p className='text-sm font-medium'>Context categorical</p><p>{groups.context_categorical?.length ?? 0}</p></Card>
        </div>

        {knobsZero && <Alert variant='destructive'>No control knobs detected. Check column naming.</Alert>}
        {knobsZero && <Accordion title='Show detection details'>
          <div className='text-xs space-y-1'>
            <p>Power matches: {(groups.power ?? []).slice(0, 10).join(', ') || 'none'}</p>
            <p>Main gas matches: {(groups.main_gas ?? []).slice(0, 10).join(', ') || 'none'}</p>
            <p>Segment gas matches: {(groups.segment_gas ?? []).slice(0, 10).join(', ') || 'none'}</p>
            {!!data.debug && <pre className='text-xs overflow-auto'>{JSON.stringify(data.debug, null, 2)}</pre>}
          </div>
        </Accordion>}
      </Card>

      <Card>
        <h3 className='text-sm font-medium tracking-tight mb-2'>Preview (first 20 rows)</h3>
        <div className='overflow-auto max-h-[420px]'>
          <table className='min-w-full text-xs'>
            <thead className='sticky top-0 bg-slate-50 z-10'><tr>{previewColumns.map(c=><th key={c} className='text-left p-2 border-b whitespace-nowrap'>{c}</th>)}</tr></thead>
            <tbody>
              {data.preview.map((row, i)=><tr key={i} className='border-b'>{previewColumns.map(c=><td key={c} className='p-2 whitespace-nowrap'>{String((row as any)[c] ?? '')}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
      </Card>
    </>}
  </div>
}
