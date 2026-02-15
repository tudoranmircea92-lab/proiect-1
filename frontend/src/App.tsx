import { RefObject, useMemo, useRef, useState } from 'react'
import { api } from './api/client'
import ColorProfileChart from './components/ColorProfileChart'
import FeatureImportanceChart from './components/FeatureImportanceChart'
import TrainingMetricsChart from './components/TrainingMetricsChart'
import type { ImportanceResponse, OptimizeResult, RegistryRun, ScanSummary, TrainRun } from './types'

const targetKeys = ['L_star_RG_mean', 'a_star_RG_mean', 'b_star_RG_mean']

type ImportanceView = 'controllable' | 'context'

const downloadSvgFromRef = (ref: RefObject<HTMLDivElement>, filename: string) => {
  const svg = ref.current?.querySelector('svg')
  if (!svg) return
  const data = new XMLSerializer().serializeToString(svg)
  const blob = new Blob([data], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function App() {
  const [tab, setTab] = useState<'TRAIN' | 'OPTIMIZE' | 'MODELS'>('TRAIN')
  const [logs, setLogs] = useState<string[]>([])
  const [scan, setScan] = useState<ScanSummary | null>(null)
  const [run, setRun] = useState<TrainRun | null>(null)
  const [registry, setRegistry] = useState<RegistryRun[]>([])
  const [importance, setImportance] = useState<ImportanceResponse | null>(null)
  const [importanceView, setImportanceView] = useState<ImportanceView>('controllable')
  const [optResult, setOptResult] = useState<OptimizeResult | null>(null)
  const [progress, setProgress] = useState(0)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [datasetPaths, setDatasetPaths] = useState<string[]>([])
  const [selectedCompartments, setSelectedCompartments] = useState<string[]>([])
  const [showL, setShowL] = useState(true)
  const [showA, setShowA] = useState(true)
  const [showB, setShowB] = useState(true)
  const [showDelta, setShowDelta] = useState(false)

  const importanceChartRef = useRef<HTMLDivElement>(null)
  const metricsChartRef = useRef<HTMLDivElement>(null)
  const profileChartRef = useRef<HTMLDivElement>(null)

  const [trainForm, setTrainForm] = useState({ product_name: 'PROD_A', model_type: 'process', split_mode: 'time-based', include_general_model: true })
  const [optForm, setOptForm] = useState({
    plateOrRun: 'P001',
    product_name: 'PROD_A',
    targetL: 61,
    targetA: 11,
    targetB: 9,
    mode: 'balanced',
    currentStateJson: '{"product_name":"PROD_A","plate":"P001","c4.pwr":55,"c4.m1g":40,"c4.m2g":40,"c4.m3g":40,"c4.s1g":10,"c5.pwr":60,"c5.m1g":30,"c7.m2g":50,"actVacuumPressure":49}',
  })

  const log = (msg: string) => setLogs((p) => [`${new Date().toLocaleTimeString()} ${msg}`, ...p].slice(0, 200))

  const filteredFeatureImportance = useMemo(() => {
    if (!importance) return []
    return importance.by_feature.filter((x) =>
      importanceView === 'controllable' ? /\.(pwr|m1g|m2g|m3g|s\d+g)$/.test(x.feature) : !/\.(pwr|m1g|m2g|m3g|s\d+g)$/.test(x.feature),
    ).slice(0, 20)
  }, [importance, importanceView])

  const trainingMetricsRows = useMemo(() => {
    if (!run?.metrics?.mae || !run?.metrics?.rmse) return []
    return targetKeys.map((target) => ({ target, mae: run.metrics.mae?.[target] ?? 0, rmse: run.metrics.rmse?.[target] ?? 0 }))
  }, [run])

  const metricsLineData = useMemo(() => trainingMetricsRows.map((x) => ({ name: x.target, mae: x.mae, rmse: x.rmse, deltaE: run?.metrics?.delta_e ?? 0 })), [trainingMetricsRows, run])

  const profileData = useMemo(() => {
    if (!optResult) return []
    const rows = [
      { series: 'L', before: optResult.before_color[targetKeys[0]], after: optResult.predicted_color[targetKeys[0]], goal: Number(optForm.targetL), deltaE: Math.abs(optResult.predicted_color[targetKeys[0]] - Number(optForm.targetL)) },
      { series: 'a', before: optResult.before_color[targetKeys[1]], after: optResult.predicted_color[targetKeys[1]], goal: Number(optForm.targetA), deltaE: Math.abs(optResult.predicted_color[targetKeys[1]] - Number(optForm.targetA)) },
      { series: 'b', before: optResult.before_color[targetKeys[2]], after: optResult.predicted_color[targetKeys[2]], goal: Number(optForm.targetB), deltaE: Math.abs(optResult.predicted_color[targetKeys[2]] - Number(optForm.targetB)) },
    ]
    const enabled = rows.filter((r) => (r.series === 'L' && showL) || (r.series === 'a' && showA) || (r.series === 'b' && showB))
    if (showDelta) {
      return enabled.map((r) => ({ ...r, before: 0, after: r.deltaE, goal: 0 }))
    }
    return enabled
  }, [optResult, optForm.targetA, optForm.targetB, optForm.targetL, showA, showB, showDelta, showL])

  const scanDataset = async () => {
    if (!selectedFiles.length) {
      log('Please choose parquet files first')
      return
    }
    try {
      log('Scanning uploaded source files...')
      const formData = new FormData()
      selectedFiles.forEach((f) => formData.append('files', f))
      const res = await api.post('/train/scan_source', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      setScan(res.data)
      setDatasetPaths(res.data.resolved_paths || [])
      if (res.data.products?.length) setTrainForm((prev) => ({ ...prev, product_name: res.data.products[0] }))
      log('Scan complete')
    } catch (e: any) {
      log(`Scan failed: ${e.message}`)
    }
  }

  const runTraining = async () => {
    if (!datasetPaths.length) {
      log('Scan source before training')
      return
    }
    setProgress(10)
    log('Training started')
    try {
      const res = await api.post('/train/run', {
        dataset_paths: datasetPaths,
        product_name: trainForm.product_name,
        model_type: trainForm.model_type,
        split_mode: trainForm.split_mode,
        split_ratios: [0.7, 0.15, 0.15],
        include_general_model: trainForm.include_general_model,
        target_columns: scan?.detected_targets?.length ? scan.detected_targets.slice(0, 3) : targetKeys,
        compute_delta_e: true,
      })
      setRun(res.data)
      setProgress(80)
      const importanceRes = await api.get(`/train/importance/${res.data.run_id}`)
      setImportance(importanceRes.data)
      await loadRuns()
      setProgress(100)
      log(`Training completed: ${res.data.run_id}`)
    } catch (e: any) {
      setProgress(0)
      log(`Training failed: ${e.message}`)
    }
  }

  const loadRuns = async () => {
    const res = await api.get('/train/runs')
    setRegistry(res.data)
  }

  const activateModel = async (runId: string) => {
    await api.post('/train/registry/activate', { run_id: runId })
    await loadRuns()
    log(`Active model set: ${runId}`)
  }

  const downloadModelArtifact = async (runId: string) => {
    const res = await api.get(`/train/artifact/${runId}`, { responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'application/octet-stream' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${runId}_model.joblib`
    a.click()
    URL.revokeObjectURL(url)
  }

  const runOptimization = async () => {
    try {
      log('Optimization started')
      const current = JSON.parse(optForm.currentStateJson)
      const res = await api.post('/optimize/run', {
        product_name: optForm.product_name,
        current_state: { ...current, plate: optForm.plateOrRun },
        target_color: { L_star_RG_mean: Number(optForm.targetL), a_star_RG_mean: Number(optForm.targetA), b_star_RG_mean: Number(optForm.targetB) },
        mode: optForm.mode,
        top_k_compartments: 5,
        coverage_threshold: 0.8,
        include_compartments: selectedCompartments,
      })
      setOptResult(res.data)
      setSelectedCompartments(res.data.selected_compartments.map((x: { compartment: string }) => x.compartment))
      log('Optimization completed')
    } catch (e: any) {
      log(`Optimization failed: ${e.message}`)
    }
  }

  const downloadRecommendationJson = () => {
    if (!optResult) return
    const blob = new Blob([JSON.stringify(optResult, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `recommendation_${optResult.created_at}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-slate-100 p-6 text-slate-900">
      <div className="mx-auto max-w-7xl rounded-2xl bg-white p-6 shadow-xl">
        <h1 className="text-3xl font-bold">Coating Process Optimizer</h1>
        <div className="mt-4 flex gap-2">{['TRAIN', 'OPTIMIZE', 'MODELS'].map((name) => <button key={name} className={`rounded-lg px-4 py-2 ${tab === name ? 'bg-indigo-600 text-white' : 'bg-slate-200'}`} onClick={() => setTab(name as 'TRAIN' | 'OPTIMIZE' | 'MODELS')}>{name}</button>)}</div>

        {tab === 'TRAIN' && <div className="mt-4 grid grid-cols-12 gap-4">
          <div className="col-span-3 rounded-xl bg-slate-50 p-4">
            <h3 className="font-semibold">Input + Config</h3>
            <label className="mt-2 block text-xs font-semibold">Browse parquet files</label>
            <input type="file" multiple accept=".parquet" className="mt-1 w-full rounded border p-2 text-xs" onChange={(e) => setSelectedFiles(Array.from(e.target.files || []))} />
            <div className="mt-2 max-h-24 overflow-auto rounded border bg-white p-2 text-xs">{selectedFiles.length ? selectedFiles.map((f) => <p key={f.name}>{f.name}</p>) : 'No files selected'}</div>
            <select className="mt-2 w-full rounded border p-2" value={trainForm.product_name} onChange={(e) => setTrainForm({ ...trainForm, product_name: e.target.value })}>{(scan?.products?.length ? scan.products : [trainForm.product_name]).map((p) => <option key={p} value={p}>{p}</option>)}</select>
            <select className="mt-2 w-full rounded border p-2" value={trainForm.model_type} onChange={(e) => setTrainForm({ ...trainForm, model_type: e.target.value })}><option value="control">CONTROL MODEL</option><option value="process">PROCESS MODEL</option></select>
            <button className="mt-2 w-full rounded bg-slate-700 p-2 text-white" onClick={scanDataset}>Scan source</button>
            <button className="mt-2 w-full rounded bg-indigo-600 p-2 text-white" onClick={runTraining}>Train</button>
            <div className="mt-2 h-2 rounded bg-slate-200"><div className="h-2 rounded bg-indigo-500" style={{ width: `${progress}%` }} /></div>
          </div>

          <div className="col-span-6 rounded-xl bg-slate-50 p-4">
            <h3 className="font-semibold">Training Metrics & Importance</h3>
            {scan && <div className="mt-2 rounded bg-white p-3 text-sm"><p><b>Rows:</b> {scan.rows}</p><p><b>Selected files:</b> {(scan.selected_files || []).join(', ')}</p><p><b>Targets:</b> {scan.detected_targets.join(', ')}</p><p><b>Columns:</b> {scan.columns.length}</p><div className="max-h-16 overflow-auto text-xs">{scan.columns.join(', ')}</div></div>}
            {run && <div className="mt-3 rounded bg-white p-3"><table className="w-full text-xs"><thead><tr><th>Target</th><th>MAE</th><th>RMSE</th></tr></thead><tbody>{trainingMetricsRows.map((r) => <tr key={r.target}><td>{r.target}</td><td>{r.mae.toFixed(4)}</td><td>{r.rmse.toFixed(4)}</td></tr>)}<tr><td>ΔE</td><td colSpan={2}>{(run.metrics.delta_e ?? 0).toFixed(4)}</td></tr></tbody></table></div>}
            <div className="mt-3 flex gap-2"><button className="rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={() => setImportanceView((v) => v === 'controllable' ? 'context' : 'controllable')}>Toggle {importanceView}</button><button className="rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={() => downloadSvgFromRef(importanceChartRef, 'importance_chart.svg')}>Download Importance Chart</button><button className="rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={() => downloadSvgFromRef(metricsChartRef, 'metrics_chart.svg')}>Download Metric Chart</button></div>
            {importance && <div className="mt-3"><FeatureImportanceChart ref={importanceChartRef} title={`Feature Importance (${importanceView})`} data={filteredFeatureImportance} /></div>}
            {run && <div className="mt-3"><TrainingMetricsChart ref={metricsChartRef} data={metricsLineData} /></div>}
          </div>

          <div className="col-span-3 rounded-xl bg-slate-50 p-4"><h3 className="font-semibold">Live logs</h3><div className="mt-2 h-[620px] overflow-auto rounded border bg-white p-2 text-xs">{logs.map((l) => <p key={l}>{l}</p>)}</div></div>
        </div>}

        {tab === 'OPTIMIZE' && <div className="mt-4 grid grid-cols-12 gap-4">
          <div className="col-span-3 rounded-xl bg-slate-50 p-4">
            <h3 className="font-semibold">Optimizer</h3>
            <input className="mt-2 w-full rounded border p-2" placeholder="Plate/Run" value={optForm.plateOrRun} onChange={(e) => setOptForm({ ...optForm, plateOrRun: e.target.value })} />
            <input className="mt-2 w-full rounded border p-2" value={optForm.product_name} onChange={(e) => setOptForm({ ...optForm, product_name: e.target.value })} />
            <div className="mt-2 grid grid-cols-3 gap-2"><input className="rounded border p-2" value={optForm.targetL} onChange={(e) => setOptForm({ ...optForm, targetL: Number(e.target.value) })} /><input className="rounded border p-2" value={optForm.targetA} onChange={(e) => setOptForm({ ...optForm, targetA: Number(e.target.value) })} /><input className="rounded border p-2" value={optForm.targetB} onChange={(e) => setOptForm({ ...optForm, targetB: Number(e.target.value) })} /></div>
            <textarea className="mt-2 h-28 w-full rounded border p-2 text-xs" value={optForm.currentStateJson} onChange={(e) => setOptForm({ ...optForm, currentStateJson: e.target.value })} />
            {['match_color', 'balanced', 'minimize_gas', 'minimize_energy'].map((m) => <label key={m} className="mt-1 flex items-center gap-2 text-sm"><input type="radio" checked={optForm.mode === m} onChange={() => setOptForm({ ...optForm, mode: m })} />{m}</label>)}
            <button className="mt-2 w-full rounded bg-indigo-600 p-2 text-white" onClick={runOptimization}>Run optimization</button>
          </div>
          <div className="col-span-6 rounded-xl bg-slate-50 p-4">
            <h3 className="font-semibold">Optimization Results</h3>
            <div className="mt-2 flex gap-2"><label className="text-xs"><input type="checkbox" checked={showL} onChange={(e) => setShowL(e.target.checked)} /> L*</label><label className="text-xs"><input type="checkbox" checked={showA} onChange={(e) => setShowA(e.target.checked)} /> a*</label><label className="text-xs"><input type="checkbox" checked={showB} onChange={(e) => setShowB(e.target.checked)} /> b*</label><label className="text-xs"><input type="checkbox" checked={showDelta} onChange={(e) => setShowDelta(e.target.checked)} /> ΔE</label><button className="rounded bg-slate-700 px-2 py-1 text-xs text-white" onClick={() => downloadSvgFromRef(profileChartRef, 'profile_chart.svg')}>Download Profile Chart</button><button className="rounded bg-slate-700 px-2 py-1 text-xs text-white" onClick={downloadRecommendationJson}>Download Recommendation JSON</button></div>
            {optResult && <><div className="mt-2 rounded bg-white p-2 text-xs">{Object.entries(optResult.recommendation).map(([k, v]) => <p key={k}>{k}: {v.toFixed(3)} (Δ {optResult.deltas[k]?.toFixed(3) ?? '0.000'})</p>)}</div><div className="mt-3"><ColorProfileChart ref={profileChartRef} data={profileData} /></div></>}
          </div>
          <div className="col-span-3 rounded-xl bg-slate-50 p-4"><h3 className="font-semibold">Relevance</h3><div className="mt-2 max-h-[620px] overflow-auto rounded border bg-white p-2 text-xs">{optResult?.selected_compartments.map((c) => <label key={c.compartment} className="flex justify-between border-b py-1"><span>{c.compartment} ({c.score.toFixed(3)})</span><input type="checkbox" checked={selectedCompartments.includes(c.compartment)} onChange={() => setSelectedCompartments((p) => p.includes(c.compartment) ? p.filter((x) => x !== c.compartment) : [...p, c.compartment])} /></label>)}</div></div>
        </div>}

        {tab === 'MODELS' && <div className="mt-4 rounded-xl bg-slate-50 p-4"><div className="mb-2 flex justify-between"><h3 className="font-semibold">Trained Models</h3><button className="rounded bg-slate-700 px-3 py-1 text-white" onClick={loadRuns}>Refresh</button></div><table className="w-full text-left text-sm"><thead><tr><th>Run</th><th>Product</th><th>Metrics</th><th>Created</th><th>Actions</th></tr></thead><tbody>{registry.map((r) => <tr key={r.run_id} className="border-t align-top"><td>{r.run_id}</td><td>{r.product_name}</td><td className="max-w-[200px] truncate">{JSON.stringify(r.metrics)}</td><td>{r.created_at}</td><td><button className="mr-2 rounded bg-indigo-600 px-2 py-1 text-white" onClick={() => activateModel(r.run_id)}>Set Active for This Product</button><button className="rounded bg-slate-700 px-2 py-1 text-white" onClick={() => downloadModelArtifact(r.run_id)}>Download Model Artifact</button></td></tr>)}</tbody></table></div>}
      </div>
    </div>
  )
}
