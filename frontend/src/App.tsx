import { RefObject, useMemo, useRef, useState } from 'react'
import { api } from './api/client'
import ColorProfileChart from './components/ColorProfileChart'
import FeatureImportanceChart from './components/FeatureImportanceChart'
import TrainingMetricsChart from './components/TrainingMetricsChart'
import type { ImportanceResponse, OptimizeResult, RegistryRun, ScanSummary, TrainRun } from './types'

const targetKeys = ['L_star_RG_mean', 'a_star_RG_mean', 'b_star_RG_mean']
const allowedExt = ['.parquet', '.csv', '.xlsx']

type ImportanceView = 'controllable' | 'context'
type ChartFormat = 'png' | 'jpeg' | 'svg'
type LogLevel = 'info' | 'success' | 'error' | 'warning'

type PreviewBlock = {
  file_name: string
  message: string
  columns: string[]
  rows: Record<string, string | number>[]
}

type LogEntry = { message: string; level: LogLevel; ts: string }

const logClass: Record<LogLevel, string> = {
  info: 'text-slate-700',
  success: 'text-emerald-700',
  error: 'text-red-700',
  warning: 'text-amber-700',
}

const downloadChartImage = async (ref: RefObject<HTMLDivElement>, filename: string, format: ChartFormat) => {
  const svg = ref.current?.querySelector('svg')
  if (!svg) return
  if (format === 'svg') {
    const data = new XMLSerializer().serializeToString(svg)
    const blob = new Blob([data], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${filename}.svg`
    a.click()
    URL.revokeObjectURL(url)
    return
  }
  const svgData = new XMLSerializer().serializeToString(svg)
  const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const img = new Image()
  img.onload = () => {
    const canvas = document.createElement('canvas')
    canvas.width = img.width || 1200
    canvas.height = img.height || 600
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, 0, 0)
      const out = canvas.toDataURL(`image/${format}`)
      const a = document.createElement('a')
      a.href = out
      a.download = `${filename}.${format}`
      a.click()
    }
    URL.revokeObjectURL(url)
  }
  img.src = url
}

export default function App() {
  const [tab, setTab] = useState<'TRAIN' | 'OPTIMIZE' | 'MODELS'>('TRAIN')
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [scan, setScan] = useState<ScanSummary | null>(null)
  const [run, setRun] = useState<TrainRun | null>(null)
  const [registry, setRegistry] = useState<RegistryRun[]>([])
  const [importance, setImportance] = useState<ImportanceResponse | null>(null)
  const [importanceView, setImportanceView] = useState<ImportanceView>('controllable')
  const [optResult, setOptResult] = useState<OptimizeResult | null>(null)
  const [progress, setProgress] = useState(0)
  const [scanProgress, setScanProgress] = useState(0)
  const [isScanning, setIsScanning] = useState(false)
  const [scanStatus, setScanStatus] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [datasetPaths, setDatasetPaths] = useState<string[]>([])
  const [fileError, setFileError] = useState('')
  const [previews, setPreviews] = useState<PreviewBlock[]>([])
  const [allowMissingProductName, setAllowMissingProductName] = useState(false)
  const [selectedCompartments, setSelectedCompartments] = useState<string[]>([])
  const [showL, setShowL] = useState(true)
  const [showA, setShowA] = useState(true)
  const [showB, setShowB] = useState(true)
  const [showDelta, setShowDelta] = useState(false)
  const [chartFormat, setChartFormat] = useState<ChartFormat>('png')
  const [exportFormat, setExportFormat] = useState<'csv' | 'xlsx'>('csv')

  const importanceChartRef = useRef<HTMLDivElement>(null)
  const metricsChartRef = useRef<HTMLDivElement>(null)
  const profileChartRef = useRef<HTMLDivElement>(null)

  const [trainForm, setTrainForm] = useState({ product_name: 'GENERAL', model_type: 'process', split_mode: 'time-based', include_general_model: true })
  const [optForm, setOptForm] = useState({
    plateOrRun: 'P001',
    product_name: 'GENERAL',
    targetL: 61,
    targetA: 11,
    targetB: 9,
    mode: 'balanced',
    currentStateJson: '{"plate":"P001","c4.pwr":55,"c4.m1g":40,"c4.m2g":40,"c4.m3g":40,"c4.s1g":10,"c5.pwr":60,"c5.m1g":30,"c7.m2g":50,"actVacuumPressure":49}',
  })

  const addLog = (message: string, level: LogLevel = 'info') => setLogs((prev) => [{ message, level, ts: new Date().toLocaleTimeString() }, ...prev].slice(0, 300))

  const scanFeatureData = useMemo(() => scan?.chart_data?.feature_importance?.slice(0, 20) ?? [], [scan])
  const scanMetricsData = useMemo(() => scan?.chart_data?.metrics ?? [], [scan])

  const filteredFeatureImportance = useMemo(() => {
    const source = importance?.by_feature?.length ? importance.by_feature : scanFeatureData
    return source.filter((x) => (importanceView === 'controllable' ? /\.(pwr|m1g|m2g|m3g|s\d+g)$/.test(x.feature) : !/\.(pwr|m1g|m2g|m3g|s\d+g)$/.test(x.feature))).slice(0, 20)
  }, [importance, importanceView, scanFeatureData])

  const metricsLineData = useMemo(() => {
    if (run?.metrics?.mae && run?.metrics?.rmse) {
      return targetKeys.map((t) => ({ name: t, mae: run.metrics.mae?.[t] ?? 0, rmse: run.metrics.rmse?.[t] ?? 0, deltaE: run.metrics.delta_e ?? 0 }))
    }
    return scanMetricsData
  }, [run, scanMetricsData])

  const profileData = useMemo(() => {
    if (!optResult) return []
    const rows = [
      { series: 'L', before: optResult.before_color[targetKeys[0]], after: optResult.predicted_color[targetKeys[0]], goal: Number(optForm.targetL), deltaE: Math.abs(optResult.predicted_color[targetKeys[0]] - Number(optForm.targetL)) },
      { series: 'a', before: optResult.before_color[targetKeys[1]], after: optResult.predicted_color[targetKeys[1]], goal: Number(optForm.targetA), deltaE: Math.abs(optResult.predicted_color[targetKeys[1]] - Number(optForm.targetA)) },
      { series: 'b', before: optResult.before_color[targetKeys[2]], after: optResult.predicted_color[targetKeys[2]], goal: Number(optForm.targetB), deltaE: Math.abs(optResult.predicted_color[targetKeys[2]] - Number(optForm.targetB)) },
    ]
    const enabled = rows.filter((r) => (r.series === 'L' && showL) || (r.series === 'a' && showA) || (r.series === 'b' && showB))
    return showDelta ? enabled.map((r) => ({ ...r, before: 0, after: r.deltaE, goal: 0 })) : enabled
  }, [optResult, optForm.targetA, optForm.targetB, optForm.targetL, showA, showB, showDelta, showL])

  const onSelectFiles = async (files: File[]) => {
    const invalid = files.filter((f) => !allowedExt.some((ext) => f.name.toLowerCase().endsWith(ext)))
    if (invalid.length > 0) {
      setFileError('Invalid file type selected. Please upload a .csv, .xlsx, or .parquet file.')
      addLog('Invalid file type selected', 'error')
      setSelectedFiles(files.filter((f) => allowedExt.some((ext) => f.name.toLowerCase().endsWith(ext))))
      return
    }
    setFileError('')
    setSelectedFiles(files)
    setAllowMissingProductName(false)

    const previewCandidates = files.filter((f) => f.name.toLowerCase().endsWith('.csv') || f.name.toLowerCase().endsWith('.xlsx'))
    if (previewCandidates.length > 0) {
      try {
        const fd = new FormData()
        previewCandidates.forEach((f) => fd.append('files', f))
        const res = await api.post('/train/preview', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
        setPreviews(res.data.previews || [])
      } catch {
        addLog('Network Error while previewing files', 'error')
      }
    } else {
      setPreviews([])
    }
  }

  const resetFileSelection = () => {
    setSelectedFiles([])
    setDatasetPaths([])
    setScan(null)
    setPreviews([])
    setAllowMissingProductName(false)
    setScanStatus('')
  }

  const scanDataset = async () => {
    if (!selectedFiles.length) {
      addLog('No files selected for scanning', 'error')
      return
    }
    try {
      setIsScanning(true)
      setScanProgress(15)
      setScanStatus('Scanning data...')
      addLog('Scanning data', 'info')
      const formData = new FormData()
      selectedFiles.forEach((f) => formData.append('files', f))
      setScanProgress(55)
      const res = await api.post('/train/scan_source', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      setScan(res.data)
      setDatasetPaths(res.data.resolved_paths || [])
      if (res.data.products?.length) {
        setTrainForm((prev) => ({ ...prev, product_name: res.data.products[0] }))
      }
      if (res.data.has_product_name === false) {
        addLog("Warning: Dataset missing 'product_name' column. Proceeding without it.", 'warning')
        setTrainForm((prev) => ({ ...prev, product_name: 'GENERAL' }))
      }
      setScanProgress(100)
      setScanStatus('Scan successful, ready for training')
      addLog('Scan successful', 'success')
      addLog('Processing completed', 'success')
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || 'Network Error'
      setScanStatus(detail)
      addLog(detail.includes('Network') ? 'Network Error' : detail, 'error')
    } finally {
      setIsScanning(false)
    }
  }

  const runTraining = async () => {
    if (!datasetPaths.length) {
      addLog('Scan data before training', 'error')
      return
    }
    if (scan?.has_product_name === false && !allowMissingProductName) {
      addLog('Please confirm Skip or Update file for missing product_name', 'warning')
      return
    }
    setProgress(10)
    addLog('Training started', 'info')
    try {
      const res = await api.post('/train/run', {
        dataset_paths: datasetPaths,
        product_name: scan?.has_product_name === false ? 'GENERAL' : trainForm.product_name,
        model_type: trainForm.model_type,
        split_mode: trainForm.split_mode,
        split_ratios: [0.7, 0.15, 0.15],
        include_general_model: trainForm.include_general_model,
        target_columns: scan?.detected_targets?.slice(0, 3)?.length ? scan.detected_targets.slice(0, 3) : targetKeys,
        compute_delta_e: true,
      })
      setRun(res.data)
      const imp = await api.get(`/train/importance/${res.data.run_id}`)
      setImportance(imp.data)
      setProgress(100)
      addLog(`Training completed: ${res.data.run_id}`, 'success')
    } catch (e: any) {
      setProgress(0)
      addLog(e?.response?.data?.detail || 'Training failed', 'error')
    }
  }

  const exportProcessedData = async () => {
    if (!datasetPaths.length) {
      addLog('Scan data before export', 'warning')
      return
    }
    const res = await api.post('/train/export-processed', { dataset_paths: datasetPaths, file_format: exportFormat }, { responseType: 'blob' })
    const blob = new Blob([res.data], { type: exportFormat === 'xlsx' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `processed_data.${exportFormat}`
    a.click()
    URL.revokeObjectURL(url)
  }

  const loadRuns = async () => setRegistry((await api.get('/train/runs')).data)

  const activateModel = async (runId: string) => {
    await api.post('/train/registry/activate', { run_id: runId })
    await loadRuns()
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
    addLog('Optimization completed', 'success')
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
        <div className="mt-4 flex gap-2">
          {['TRAIN', 'OPTIMIZE', 'MODELS'].map((name) => (
            <button key={name} className={`rounded-lg px-4 py-2 ${tab === name ? 'bg-indigo-600 text-white' : 'bg-slate-200'}`} onClick={() => setTab(name as 'TRAIN' | 'OPTIMIZE' | 'MODELS')}>{name}</button>
          ))}
        </div>

        {tab === 'TRAIN' && <div className="mt-4 grid grid-cols-12 gap-4">
          <div className="col-span-3 rounded-xl bg-slate-50 p-4">
            <h3 className="font-semibold">Input + Config</h3>
            <label className="mt-2 block text-xs font-semibold">Browse data files</label>
            <input type="file" multiple accept=".parquet,.csv,.xlsx" className="mt-1 w-full rounded border p-2 text-xs" onChange={(e) => onSelectFiles(Array.from(e.target.files || []))} />
            {fileError && <p className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">{fileError}</p>}
            <div className="mt-2 max-h-24 overflow-auto rounded border bg-white p-2 text-xs">{selectedFiles.length ? selectedFiles.map((f) => <p key={f.name}>{f.name}</p>) : 'No files selected'}</div>

            {isScanning && <div className="mt-2 animate-pulse text-xs text-slate-600">Scanning...</div>}
            <div className="mt-2 h-2 rounded bg-slate-200"><div className="h-2 rounded bg-indigo-500" style={{ width: `${scanProgress}%` }} /></div>
            {scanStatus && <p className="mt-2 text-xs font-semibold text-indigo-700">{scanStatus}</p>}

            {scan?.has_product_name === false && (
              <div className="mt-2 rounded border border-amber-300 bg-amber-50 p-2 text-xs">
                <p>{scan.missing_product_name_message}</p>
                <p className="mt-1 text-slate-600" title="Add a product_name column in CSV/Excel as a text field for each row.">Guidance: add a `product_name` column to each row (e.g., PROD_A).</p>
                <p className="mt-1 text-slate-600">Recommended columns: {scan.recommended_columns?.join(', ')}.</p>
                <div className="mt-2 flex gap-2">
                  <button className="rounded bg-indigo-600 px-2 py-1 text-white" onClick={() => { setAllowMissingProductName(true); addLog("Warning: Dataset missing 'product_name' column. Proceeding without it.", 'warning') }}>Skip</button>
                  <button className="rounded bg-slate-700 px-2 py-1 text-white" onClick={resetFileSelection}>Update file</button>
                </div>
              </div>
            )}

            <select className="mt-2 w-full rounded border p-2" value={trainForm.product_name} onChange={(e) => setTrainForm({ ...trainForm, product_name: e.target.value })}>
              {(scan?.products?.length ? scan.products : ['GENERAL']).map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select className="mt-2 w-full rounded border p-2" value={trainForm.model_type} onChange={(e) => setTrainForm({ ...trainForm, model_type: e.target.value })}><option value="control">CONTROL MODEL</option><option value="process">PROCESS MODEL</option></select>
            <button className="mt-2 w-full rounded bg-slate-700 p-2 text-white" onClick={scanDataset}>Scan Data</button>
            <button className="mt-2 w-full rounded bg-indigo-600 p-2 text-white" onClick={runTraining}>Train</button>
            <div className="mt-2 h-2 rounded bg-slate-200"><div className="h-2 rounded bg-indigo-500" style={{ width: `${progress}%` }} /></div>
          </div>

          <div className="col-span-6 rounded-xl bg-slate-50 p-4">
            <h3 className="font-semibold">Training Metrics & Importance</h3>
            {scan && <div className="mt-2 rounded bg-white p-3 text-sm"><p><b>Status:</b> {scan.status || 'Scan successful'}</p><p><b>Rows:</b> {scan.rows}</p><p><b>Targets:</b> {scan.detected_targets.join(', ')}</p><p><b>Columns:</b> {scan.columns.length}</p>{scan.has_product_name === false && <p className="mt-1 font-semibold text-amber-700">Missing product_name column</p>}</div>}

            {scan?.preview_rows && scan.preview_rows.length > 0 && (
              <div className="mt-2 rounded bg-white p-2 text-xs">
                <p className="font-semibold">Showing first 5 rows of your file.</p>
                <div className="mt-1 overflow-auto">
                  <table className="w-full text-left text-[11px]"><thead><tr>{Object.keys(scan.preview_rows[0]).map((c) => <th key={c} className="border-b pr-2">{c}</th>)}</tr></thead><tbody>{scan.preview_rows.map((r, i) => <tr key={i}>{Object.keys(scan.preview_rows?.[0] || {}).map((c) => <td key={c} className="border-b pr-2">{String(r[c] ?? '')}</td>)}</tr>)}</tbody></table>
                </div>
              </div>
            )}

            {previews.length > 0 && previews.map((p) => <div key={p.file_name} className="mt-2 rounded bg-white p-2 text-xs"><p className="font-semibold">{p.file_name}</p><p>{p.message}</p></div>)}

            <div className="mt-3 flex gap-2">
              <button className="rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={() => setImportanceView((v) => (v === 'controllable' ? 'context' : 'controllable'))}>Toggle {importanceView}</button>
              <select className="rounded border px-2 py-1 text-xs" value={chartFormat} onChange={(e) => setChartFormat(e.target.value as ChartFormat)}><option value="png">PNG</option><option value="jpeg">JPEG</option><option value="svg">SVG</option></select>
              <button className="rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={() => downloadChartImage(importanceChartRef, 'importance_chart', chartFormat)}>Download Importance Chart</button>
              <button className="rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={() => downloadChartImage(metricsChartRef, 'metrics_chart', chartFormat)}>Download Metric Chart</button>
            </div>
            {filteredFeatureImportance.length > 0 && <div className="mt-3"><FeatureImportanceChart ref={importanceChartRef} title={`Feature Importance (${importanceView})`} data={filteredFeatureImportance} /></div>}
            {metricsLineData.length > 0 && <div className="mt-3"><TrainingMetricsChart ref={metricsChartRef} data={metricsLineData} /></div>}

            <div className="mt-3 flex items-center gap-2">
              <select className="rounded border px-2 py-1 text-xs" value={exportFormat} onChange={(e) => setExportFormat(e.target.value as 'csv' | 'xlsx')}><option value="csv">CSV</option><option value="xlsx">XLSX</option></select>
              <button className="rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={exportProcessedData}>Download Processed Data</button>
            </div>
          </div>

          <div className="col-span-3 rounded-xl bg-slate-50 p-4"><h3 className="font-semibold">Live logs</h3><div className="mt-2 h-[620px] overflow-auto rounded border bg-white p-2 text-xs">{logs.map((l, idx) => <p key={`${l.ts}-${idx}`} className={logClass[l.level]}>{l.ts} {l.message}</p>)}</div></div>
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
            <div className="mt-2 flex gap-2"><label className="text-xs"><input type="checkbox" checked={showL} onChange={(e) => setShowL(e.target.checked)} /> L*</label><label className="text-xs"><input type="checkbox" checked={showA} onChange={(e) => setShowA(e.target.checked)} /> a*</label><label className="text-xs"><input type="checkbox" checked={showB} onChange={(e) => setShowB(e.target.checked)} /> b*</label><label className="text-xs"><input type="checkbox" checked={showDelta} onChange={(e) => setShowDelta(e.target.checked)} /> ΔE</label><button className="rounded bg-slate-700 px-2 py-1 text-xs text-white" onClick={() => downloadChartImage(profileChartRef, 'profile_chart', chartFormat)}>Download Profile Chart</button><button className="rounded bg-slate-700 px-2 py-1 text-xs text-white" onClick={downloadRecommendationJson}>Download Recommendation JSON</button></div>
            {optResult && <><div className="mt-2 rounded bg-white p-2 text-xs">{Object.entries(optResult.recommendation).map(([k, v]) => <p key={k}>{k}: {v.toFixed(3)} (Δ {optResult.deltas[k]?.toFixed(3) ?? '0.000'})</p>)}</div><div className="mt-3"><ColorProfileChart ref={profileChartRef} data={profileData} /></div></>}
          </div>
          <div className="col-span-3 rounded-xl bg-slate-50 p-4"><h3 className="font-semibold">Relevance</h3><div className="mt-2 max-h-[620px] overflow-auto rounded border bg-white p-2 text-xs">{optResult?.selected_compartments.map((c) => <label key={c.compartment} className="flex justify-between border-b py-1"><span>{c.compartment} ({c.score.toFixed(3)})</span><input type="checkbox" checked={selectedCompartments.includes(c.compartment)} onChange={() => setSelectedCompartments((p) => p.includes(c.compartment) ? p.filter((x) => x !== c.compartment) : [...p, c.compartment])} /></label>)}</div></div>
        </div>}

        {tab === 'MODELS' && <div className="mt-4 rounded-xl bg-slate-50 p-4"><div className="mb-2 flex justify-between"><h3 className="font-semibold">Trained Models</h3><button className="rounded bg-slate-700 px-3 py-1 text-white" onClick={loadRuns}>Refresh</button></div><table className="w-full text-left text-sm"><thead><tr><th>Run</th><th>Product</th><th>Metrics</th><th>Created</th><th>Actions</th></tr></thead><tbody>{registry.map((r) => <tr key={r.run_id} className="border-t align-top"><td>{r.run_id}</td><td>{r.product_name}</td><td className="max-w-[200px] truncate">{JSON.stringify(r.metrics)}</td><td>{r.created_at}</td><td><button className="mr-2 rounded bg-indigo-600 px-2 py-1 text-white" onClick={() => activateModel(r.run_id)}>Set Active for This Product</button><button className="rounded bg-slate-700 px-2 py-1 text-white" onClick={() => downloadModelArtifact(r.run_id)}>Download Model Artifact</button></td></tr>)}</tbody></table></div>}
      </div>
    </div>
  )
}
