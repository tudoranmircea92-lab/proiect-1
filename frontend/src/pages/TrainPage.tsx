import { Download, Play } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Accordion, Alert, Badge, Button, Card, Input, Progress, Select, Skeleton, Switch } from '../components/ui'
import { api } from '../lib/api'
import { useDataset } from '../lib/datasetContext'
import { runJob } from '../lib/jobs'

const CATHODE_RE = /^(c\d+)[._]/i

function groupByCathode(cols: string[]) {
  const by: Record<string, string[]> = {}
  cols.forEach((c) => {
    const m = c.match(CATHODE_RE)
    const key = m ? m[1].toLowerCase() : 'other'
    if (!by[key]) by[key] = []
    by[key].push(c)
  })
  return Object.entries(by).sort((a, b) => a[0].localeCompare(b[0], undefined, { numeric: true }))
}

export function TrainPage() {
  const { datasetId, datasetSummary, groupedColumns, datasetName, globalFilters, setModelTrained } = useDataset()
  const [models, setModels] = useState<string[]>([])
  const [estimatorType, setEstimatorType] = useState('hist_gradient_boosting')
  const [trainingMode, setTrainingMode] = useState<'fast' | 'balanced' | 'maximum_accuracy'>('balanced')
  const [split, setSplit] = useState<'time' | 'random' | 'by_product'>('time')
  const [stratifyByProduct, setStratifyByProduct] = useState(false)
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
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')

  useEffect(() => {
    api.get('/api/models').then((r) => setModels(r.data.models))
  }, [])

  const featureGroups = useMemo(() => {
    const g = groupedColumns || {}
    const power = toggles.include_power ? (g.power || []) : []
    const main = toggles.include_main_gas ? (g.main_gas || []) : []
    const seg = toggles.include_segment_gas ? (g.segment_gas || []) : []
    const alt = toggles.include_main_gas_alt ? (g.main_gas_alt || []) : []
    const ctxNum = toggles.include_context_numeric ? (g.context_numeric || []) : []
    const ctxCat = toggles.include_context_categorical ? (g.context_categorical || []) : []
    return { power, main, seg, alt, ctxNum, ctxCat }
  }, [groupedColumns, toggles])

  const summary = useMemo(() => {
    const totalRows = datasetSummary?.rows || 0
    const trainRows = Math.floor(totalRows * ratio)
    const valRows = totalRows - trainRows
    const totalFeatures = featureGroups.power.length + featureGroups.main.length + featureGroups.seg.length + featureGroups.alt.length + featureGroups.ctxNum.length + featureGroups.ctxCat.length
    const controlKnobs = featureGroups.power.length + featureGroups.main.length + featureGroups.seg.length + featureGroups.alt.length
    const targets = groupedColumns?.targets?.length || 0
    return { totalRows, trainRows, valRows, totalFeatures, controlKnobs, targets }
  }, [datasetSummary, ratio, featureGroups, groupedColumns])

  const canTrain = !!datasetId && summary.controlKnobs > 0 && summary.targets > 0 && !loading

  const train = async () => {
    if (!datasetId) {
      setError('Load data first')
      return
    }
    if (summary.controlKnobs === 0 || summary.targets === 0) {
      setError('Cannot train: control knobs or targets are zero.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await runJob(
        '/api/train',
        {
          dataset_id: datasetId,
          filter: { products: globalFilters.products, thicknesses: globalFilters.thicknesses, date_from: globalFilters.dateFrom || null, date_to: globalFilters.dateTo || null },
          config: {
            estimator_type: estimatorType,
            training_mode: trainingMode,
            split: { method: split, ratio, random_seed: seed, stratify_by_product: stratifyByProduct },
            features: toggles,
          },
        },
        ({ progress, stage }) => {
          setProgress(progress)
          setStage(stage)
        }
      )
      setResult(res)
      setModelTrained(true)
    } catch (e: any) {
      setError(e.message || 'Train failed')
    } finally {
      setLoading(false)
    }
  }

  const fmt = (v: any) => (v === null || v === undefined || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(4))
  const targetRows = useMemo(
    () =>
      result
        ? Object.entries(result.metrics_per_target).map(([target, m]: any) => ({
            target,
            trainMae: m.train_mae,
            valMae: m.validation_mae,
          }))
        : [],
    [result]
  )

  const chartData = useMemo(() => targetRows.map((r) => ({ target: r.target, valMae: r.valMae })), [targetRows])

  const exportTrainingReport = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'training_report.json'
    a.click()
  }

  return (
    <div className="space-y-6">
      {!datasetId && <Alert variant="destructive">Load data first.</Alert>}
      {(summary.controlKnobs === 0 || summary.targets === 0) && datasetId && (
        <Alert variant="destructive">No control knobs or targets detected. Check dataset column naming and profile details.</Alert>
      )}

      <Card className="space-y-2">
        <h3 className="text-sm font-medium tracking-tight">Training summary</h3>
        <p className="text-sm text-slate-500">Dataset: {datasetName || '—'}</p>
        <p className="text-sm">Rows: {summary.totalRows} total → {summary.trainRows} train / {summary.valRows} validation</p>
        <p className="text-sm">
          Features: {summary.totalFeatures} total (Power: {featureGroups.power.length}, MainGas: {featureGroups.main.length + featureGroups.alt.length}, SegmentGas: {featureGroups.seg.length}, Context: {featureGroups.ctxNum.length + featureGroups.ctxCat.length})
        </p>
        <div className="flex gap-2 items-center">
          <Badge>Control knobs: {summary.controlKnobs}</Badge>
          <Badge>Targets: {summary.targets}</Badge>
        </div>
      </Card>

      <Card className="space-y-3">
        <h3 className="text-sm font-medium tracking-tight">Feature groups</h3>
        <div className="grid md:grid-cols-2 gap-2 text-sm">
          <div>Power knobs: {featureGroups.power.length}</div>
          <div>Main gas knobs: {featureGroups.main.length + featureGroups.alt.length}</div>
          <div>Segment gas knobs: {featureGroups.seg.length}</div>
          <div>Context numeric: {featureGroups.ctxNum.length}</div>
          <div>Context categorical: {featureGroups.ctxCat.length}</div>
        </div>
        <Accordion title="Expand feature columns by cathode">
          {[
            ['Power knobs', featureGroups.power],
            ['Main gas knobs', [...featureGroups.main, ...featureGroups.alt]],
            ['Segment gas knobs', featureGroups.seg],
            ['Context numeric', featureGroups.ctxNum],
            ['Context categorical', featureGroups.ctxCat],
          ].map(([title, cols]) => (
            <div key={title as string} className="mb-3">
              <p className="text-sm font-medium">{title as string}</p>
              {groupByCathode(cols as string[]).map(([cathode, names]) => (
                <p key={cathode} className="text-xs text-slate-600">{cathode}: {names.join(', ')}</p>
              ))}
            </div>
          ))}
        </Accordion>
      </Card>

      <div className="grid md:grid-cols-2 gap-6">
        <Card className="space-y-3">
          <h3 className="text-sm font-medium tracking-tight">Model settings</h3>
          <div className="space-y-2">
            <label className="text-sm">Training mode</label>
            <Select value={trainingMode} onChange={(e: any) => setTrainingMode(e.target.value)} disabled={loading}>
              <option value="fast">Fast (dev)</option>
              <option value="balanced">Balanced (default)</option>
              <option value="maximum_accuracy">Maximum accuracy</option>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm">Estimator type</label>
            <Select value={estimatorType} onChange={(e: any) => setEstimatorType(e.target.value)} disabled={loading}>
              {models.map((m) => <option key={m}>{m}</option>)}
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm">Split</label>
            <Select value={split} onChange={(e: any) => setSplit(e.target.value)} disabled={loading}>
              <option value="time">time</option>
              <option value="random">random</option>
              <option value="by_product">by_product</option>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm">Split ratio: {ratio.toFixed(2)}</label>
            <Input type="range" min="0.5" max="0.95" step="0.01" value={ratio} onChange={(e: any) => setRatio(Number(e.target.value))} disabled={loading} />
          </div>
          <div className="space-y-2">
            <label className="text-sm">Random seed</label>
            <Input type="number" value={seed} onChange={(e: any) => setSeed(Number(e.target.value))} disabled={loading} />
          </div>
          <div className="flex items-center justify-between text-sm">
            <span>Stratify by product (random split)</span>
            <Switch checked={stratifyByProduct} onCheckedChange={(v:boolean)=>setStratifyByProduct(v)} />
          </div>
        </Card>

        <Card className="space-y-2">
          <h3 className="text-sm font-medium tracking-tight">Features</h3>
          {Object.entries(toggles).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between text-sm">
              <span>{k}</span>
              <Switch checked={v} onCheckedChange={(nv: boolean) => setToggles({ ...toggles, [k]: nv })} />
            </div>
          ))}
        </Card>
      </div>

      <Card className="space-y-3">
        {loading && (
          <>
            <Progress value={progress} />
            <p className="text-sm text-slate-500">{stage}</p>
          </>
        )}
        {error && <Alert variant="destructive">{error}</Alert>}
        <Button onClick={train} disabled={!canTrain}>
          <Play size={16} className="inline mr-1" />Train model
        </Button>
      </Card>

      {loading && <div className="grid md:grid-cols-4 gap-3">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20" />)}</div>}

      {result && (
        <>
          <Card className="space-y-3">
            <h3 className="text-sm font-medium tracking-tight">Training Results</h3>
            <div className="grid md:grid-cols-4 gap-3">
              <Card className="p-3"><p className="text-sm">Mean absolute error (L)</p><p className="text-2xl font-semibold">{fmt(result.metrics_summary?.mae_L)}</p></Card>
              <Card className="p-3"><p className="text-sm">Mean absolute error (a)</p><p className="text-2xl font-semibold">{fmt(result.metrics_summary?.mae_a)}</p></Card>
              <Card className="p-3"><p className="text-sm">Mean absolute error (b)</p><p className="text-2xl font-semibold">{fmt(result.metrics_summary?.mae_b)}</p></Card>
              <Card className="p-3"><p className="text-sm">Overall mean error</p><p className="text-2xl font-semibold">{fmt(result.metrics_summary?.overall_mean_error)}</p></Card>
            </div>

            <Card className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead><tr className="border-b"><th className="text-left p-2">Target</th><th className="text-left p-2">Train MAE</th><th className="text-left p-2">Validation MAE</th></tr></thead>
                <tbody>
                  {targetRows.map((r: any) => (
                    <tr key={r.target} className="border-b"><td className="p-2">{r.target}</td><td className="p-2">{fmt(r.trainMae)}</td><td className="p-2">{fmt(r.valMae)}</td></tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <Card className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="target" interval={0} angle={-45} textAnchor="end" height={100} /><YAxis /><Tooltip /><Bar dataKey="valMae" fill="#2563eb" /></BarChart>
              </ResponsiveContainer>
            </Card>
          </Card>

          <Card className="space-y-2">
            <h3 className="text-sm font-medium tracking-tight">Model info</h3>
            <p className="text-sm">Model type: {result.estimator_type}</p>
            <p className="text-sm">Training date/time: {result.trained_at}</p>
            <p className="text-sm">Dataset used: {result.dataset_id}</p>
            <p className="text-sm">Number of features: {result.feature_count}</p>
            <p className="text-sm">Random seed: {result.random_seed}</p>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => window.open(`http://localhost:8000/api/artifacts/${result.artifact_id}/download`)}>
                <Download size={16} className="inline mr-1" />Download model
              </Button>
              <Button variant="secondary" onClick={exportTrainingReport}>Export training report JSON</Button>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
