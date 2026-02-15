import { useMemo, useRef, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from './api/client'
import type { ImportanceResponse, OptimizeResult, RegistryRun, ScanSummary, TrainRun } from './types'

const targetKeys = ['L_star_RG_mean', 'a_star_RG_mean', 'b_star_RG_mean']

type ImportanceView = 'controllable' | 'context'

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
  const [availableCompartments, setAvailableCompartments] = useState<string[]>([])
  const [selectedCompartments, setSelectedCompartments] = useState<string[]>([])
  const [graphSelector, setGraphSelector] = useState<'all' | 'L' | 'a' | 'b' | 'deltaE'>('all')

  const chartRef = useRef<HTMLDivElement>(null)

  const [trainForm, setTrainForm] = useState({
    path: 'backend/app/data/sample_merged.parquet',
    product_name: 'PROD_A',
    model_type: 'process',
    split_mode: 'time-based',
    include_general_model: true,
  })

  const [optForm, setOptForm] = useState({
    plateOrRun: 'P001',
    product_name: 'PROD_A',
    targetL: 61,
    targetA: 11,
    targetB: 9,
    mode: 'balanced',
    currentStateJson: '{"product_name":"PROD_A","plate":"P001","c4.pwr":55,"c4.m1g":40,"c4.m2g":40,"c4.m3g":40,"c4.s1g":10,"c5.pwr":60,"c5.m1g":30,"c7.m2g":50,"actVacuumPressure":49}',
  })

  const log = (msg: string) => setLogs((p) => [`${new Date().toLocaleTimeString()} ${msg}`, ...p].slice(0, 120))

  const filteredFeatureImportance = useMemo(() => {
    if (!importance) return []
    return importance.by_feature
      .filter((x) => importanceView === 'controllable'
        ? /\.(pwr|m1g|m2g|m3g|s\d+g)$/.test(x.feature)
        : !/\.(pwr|m1g|m2g|m3g|s\d+g)$/.test(x.feature))
      .slice(0, 15)
  }, [importance, importanceView])

  const trainingMetricsRows = useMemo(() => {
    if (!run?.metrics?.mae || !run?.metrics?.rmse) return []
    return targetKeys.map((target) => ({
      target,
      mae: run.metrics.mae?.[target],
      rmse: run.metrics.rmse?.[target],
    }))
  }, [run])

  const profileData = useMemo(() => {
    if (!optResult) return []
    const targets: Array<{ key: string; label: 'L' | 'a' | 'b'; goal: number }> = [
      { key: targetKeys[0], label: 'L', goal: Number(optForm.targetL) },
      { key: targetKeys[1], label: 'a', goal: Number(optForm.targetA) },
      { key: targetKeys[2], label: 'b', goal: Number(optForm.targetB) },
    ]
    const mapped = targets.map((t) => {
      const before = optResult.before_color[t.key]
      const after = optResult.predicted_color[t.key]
      return { series: t.label, before, after, goal: t.goal, deltaE: Math.abs(after - t.goal) }
    })
    if (graphSelector === 'all') return mapped
    if (graphSelector === 'deltaE') return mapped.map((m) => ({ ...m, before: 0, after: m.deltaE, goal: 0 }))
    return mapped.filter((m) => m.series === graphSelector)
  }, [optResult, optForm.targetA, optForm.targetB, optForm.targetL, graphSelector])

  const scanDataset = async () => {
    log('Scanning source...')
    try {
      const res = await api.post('/train/scan_source', { paths: [trainForm.path] })
      setScan(res.data)
      if (res.data.products?.length) {
        setTrainForm((prev) => ({ ...prev, product_name: res.data.products[0] }))
      }
      log('Scan complete')
    } catch (e: any) {
      log(`Scan failed: ${e.message}`)
    }
  }

  const runTraining = async () => {
    setProgress(10)
    log('Training started')
    try {
      const res = await api.post('/train/run', {
        dataset_paths: [trainForm.path],
        product_name: trainForm.product_name,
        model_type: trainForm.model_type,
        split_mode: trainForm.split_mode,
        split_ratios: [0.7, 0.15, 0.15],
        include_general_model: trainForm.include_general_model,
        target_columns: scan?.detected_targets?.length ? scan.detected_targets.slice(0, 3) : targetKeys,
        compute_delta_e: true,
      })
      setProgress(70)
      setRun(res.data)
      await loadImportance(res.data.run_id)
      await loadRuns()
      setProgress(100)
      log(`Training completed: ${res.data.run_id}`)
    } catch (e: any) {
      log(`Training failed: ${e.message}`)
      setProgress(0)
    }
  }

  const loadRuns = async () => {
    const res = await api.get('/train/runs')
    setRegistry(res.data)
  }

  const activateModel = async (runId: string) => {
    await api.post('/train/registry/activate', { run_id: runId })
    await loadRuns()
    log(`Active model updated: ${runId}`)
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

  const loadImportance = async (runId: string) => {
    const res = await api.get(`/train/importance/${runId}`)
    setImportance(res.data)
  }

  const runOptimization = async () => {
    log('Optimization started')
    const current = JSON.parse(optForm.currentStateJson)
    const include = selectedCompartments.length ? selectedCompartments : []
    const res = await api.post('/optimize/run', {
      product_name: optForm.product_name,
      current_state: { ...current, plate: optForm.plateOrRun },
      target_color: { L_star_RG_mean: Number(optForm.targetL), a_star_RG_mean: Number(optForm.targetA), b_star_RG_mean: Number(optForm.targetB) },
      mode: optForm.mode,
      top_k_compartments: 5,
      coverage_threshold: 0.8,
      include_compartments: include,
      exclude_compartments: availableCompartments.filter((c) => !selectedCompartments.includes(c)),
    })
    setOptResult(res.data)
    const comps = res.data.selected_compartments.map((x: { compartment: string }) => x.compartment)
    setAvailableCompartments(comps)
    setSelectedCompartments(comps)
    log('Optimization completed')
  }

  const toggleCompartment = (comp: string) => {
    setSelectedCompartments((prev) => prev.includes(comp) ? prev.filter((x) => x !== comp) : [...prev, comp])
  }

  const downloadOptimizationJson = () => {
    if (!optResult) return
    const blob = new Blob([JSON.stringify(optResult, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `optimization_${optResult.created_at}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadChartSvg = () => {
    const svg = chartRef.current?.querySelector('svg')
    if (!svg) return
    const data = new XMLSerializer().serializeToString(svg)
    const blob = new Blob([data], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'color_profile_chart.svg'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-slate-100 p-6 text-slate-900">
      <div className="mx-auto max-w-7xl rounded-2xl bg-white p-6 shadow-xl">
        <h1 className="text-2xl font-semibold">Coating Process Optimizer</h1>
        <p className="text-sm text-slate-500">Industrial dashboard for TRAIN and OPTIMIZE workflows</p>

        <div className="mt-4 flex gap-2">
          {['TRAIN', 'OPTIMIZE', 'MODELS'].map((name) => (
            <button key={name} onClick={() => setTab(name as 'TRAIN' | 'OPTIMIZE' | 'MODELS')} className={`rounded-lg px-4 py-2 text-sm font-medium ${tab === name ? 'bg-indigo-600 text-white' : 'bg-slate-200'}`}>{name}</button>
          ))}
        </div>

        {tab === 'TRAIN' && (
          <div className="mt-4 grid grid-cols-12 gap-4">
            <div className="col-span-3 rounded-xl bg-slate-50 p-4">
              <h3 className="font-semibold">Source + Filters</h3>
              <input className="mt-2 w-full rounded border p-2" value={trainForm.path} onChange={(e) => setTrainForm({ ...trainForm, path: e.target.value })} />
              <select className="mt-2 w-full rounded border p-2" value={trainForm.product_name} onChange={(e) => setTrainForm({ ...trainForm, product_name: e.target.value })}>
                {(scan?.products?.length ? scan.products : [trainForm.product_name]).map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <select className="mt-2 w-full rounded border p-2" value={trainForm.model_type} onChange={(e) => setTrainForm({ ...trainForm, model_type: e.target.value })}>
                <option value="control">CONTROL MODEL</option>
                <option value="process">PROCESS MODEL</option>
              </select>
              <button className="mt-2 w-full rounded bg-slate-700 p-2 text-white" onClick={scanDataset}>Scan source</button>
              <button className="mt-2 w-full rounded bg-indigo-600 p-2 text-white" onClick={runTraining}>Train model</button>
              <div className="mt-2 h-2 rounded bg-slate-200"><div className="h-2 rounded bg-indigo-500" style={{ width: `${progress}%` }} /></div>
            </div>

            <div className="col-span-6 rounded-xl bg-slate-50 p-4">
              <h3 className="font-semibold">Dataset preview + Training results</h3>
              {scan && (
                <div className="mt-2 rounded bg-white p-3 text-sm">
                  <p><b>Rows:</b> {scan.rows}</p>
                  <p><b>Products:</b> {scan.products.join(', ') || 'n/a'}</p>
                  <p><b>Target columns:</b> {scan.detected_targets.join(', ') || 'n/a'}</p>
                  <p><b>Columns ({scan.columns.length}):</b></p>
                  <div className="max-h-20 overflow-auto rounded border p-2 text-xs">{scan.columns.join(', ')}</div>
                </div>
              )}

              {run && (
                <div className="mt-3 rounded bg-white p-3">
                  <h4 className="text-sm font-semibold">Training metrics</h4>
                  <table className="mt-2 w-full text-left text-xs"><thead><tr><th>Target</th><th>MAE</th><th>RMSE</th></tr></thead><tbody>
                    {trainingMetricsRows.map((r) => <tr key={r.target} className="border-t"><td>{r.target}</td><td>{r.mae?.toFixed(4)}</td><td>{r.rmse?.toFixed(4)}</td></tr>)}
                    <tr className="border-t font-semibold"><td>ΔE</td><td colSpan={2}>{run.metrics.delta_e?.toFixed(4) ?? 'n/a'}</td></tr>
                  </tbody></table>
                </div>
              )}

              {importance && (
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div className="rounded bg-white p-2">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-xs font-semibold">Feature importance ({importanceView})</p>
                      <button onClick={() => setImportanceView((v) => v === 'controllable' ? 'context' : 'controllable')} className="rounded bg-slate-700 px-2 py-1 text-xs text-white">Toggle view</button>
                    </div>
                    <div className="h-52"><ResponsiveContainer><BarChart data={filteredFeatureImportance}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="feature" hide /><YAxis/><Tooltip/><Bar dataKey="importance" fill="#4f46e5"/></BarChart></ResponsiveContainer></div>
                  </div>
                  <div className="rounded bg-white p-2">
                    <p className="text-xs font-semibold">Compartment relevance</p>
                    <div className="h-52"><ResponsiveContainer><BarChart data={importance.by_compartment.slice(0, 10)}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="compartment"/><YAxis/><Tooltip/><Bar dataKey="importance" fill="#0ea5e9"/></BarChart></ResponsiveContainer></div>
                    <p className="text-xs">Controllable share: {(importance.share.controllable * 100).toFixed(1)}% | Context: {(importance.share.context * 100).toFixed(1)}%</p>
                  </div>
                </div>
              )}
            </div>

            <div className="col-span-3 rounded-xl bg-slate-50 p-4">
              <h3 className="font-semibold">Live logs</h3>
              <div className="mt-2 h-[520px] overflow-auto rounded border bg-white p-2 text-xs">
                {logs.map((l) => <p key={l}>{l}</p>)}
              </div>
            </div>
          </div>
        )}

        {tab === 'OPTIMIZE' && (
          <div className="mt-4 grid grid-cols-12 gap-4">
            <div className="col-span-3 rounded-xl bg-slate-50 p-4">
              <h3 className="font-semibold">Optimization form</h3>
              <input className="mt-2 w-full rounded border p-2" placeholder="Plate / Run" value={optForm.plateOrRun} onChange={(e) => setOptForm({ ...optForm, plateOrRun: e.target.value })} />
              <input className="mt-2 w-full rounded border p-2" value={optForm.product_name} onChange={(e) => setOptForm({ ...optForm, product_name: e.target.value })} />
              <textarea className="mt-2 h-32 w-full rounded border p-2 text-xs" value={optForm.currentStateJson} onChange={(e) => setOptForm({ ...optForm, currentStateJson: e.target.value })} />
              <div className="mt-2 grid grid-cols-3 gap-2">
                <input className="rounded border p-2" value={optForm.targetL} onChange={(e) => setOptForm({ ...optForm, targetL: Number(e.target.value) })} />
                <input className="rounded border p-2" value={optForm.targetA} onChange={(e) => setOptForm({ ...optForm, targetA: Number(e.target.value) })} />
                <input className="rounded border p-2" value={optForm.targetB} onChange={(e) => setOptForm({ ...optForm, targetB: Number(e.target.value) })} />
              </div>
              <div className="mt-2 space-y-1 text-sm">
                {['match_color', 'balanced', 'minimize_gas', 'minimize_energy'].map((m) => (
                  <label key={m} className="flex items-center gap-2"><input type="radio" checked={optForm.mode === m} onChange={() => setOptForm({ ...optForm, mode: m })} />{m}</label>
                ))}
              </div>
              <button className="mt-2 w-full rounded bg-indigo-600 p-2 text-white" onClick={runOptimization}>Run optimization</button>
            </div>

            <div className="col-span-6 rounded-xl bg-slate-50 p-4">
              <h3 className="font-semibold">Optimization results</h3>
              <div className="mt-2 flex gap-2">
                <button className="rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={downloadOptimizationJson}>Download JSON</button>
                <button className="rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={downloadChartSvg}>Download chart</button>
                <select className="rounded border px-2 py-1 text-xs" value={graphSelector} onChange={(e) => setGraphSelector(e.target.value as 'all' | 'L' | 'a' | 'b' | 'deltaE')}>
                  <option value="all">L*, a*, b*</option>
                  <option value="L">L*</option>
                  <option value="a">a*</option>
                  <option value="b">b*</option>
                  <option value="deltaE">ΔE</option>
                </select>
              </div>

              {optResult && (
                <>
                  <div className="mt-2 rounded bg-white p-3 text-sm">
                    <p><b>Predicted after:</b> L {optResult.predicted_color[targetKeys[0]]?.toFixed(3)}, a {optResult.predicted_color[targetKeys[1]]?.toFixed(3)}, b {optResult.predicted_color[targetKeys[2]]?.toFixed(3)}</p>
                    <p><b>Score (ΔE-like):</b> {optResult.score.toFixed(4)}</p>
                  </div>
                  <div ref={chartRef} className="mt-3 h-64 rounded bg-white p-2">
                    <ResponsiveContainer>
                      <LineChart data={profileData}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="series"/><YAxis/><Tooltip/><Legend/><Line dataKey="before" stroke="#334155"/><Line dataKey="after" stroke="#4f46e5"/><Line dataKey="goal" stroke="#16a34a"/></LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-3 max-h-52 overflow-auto rounded bg-white p-2 text-xs">
                    {Object.entries(optResult.recommendation).map(([k, v]) => (
                      <p key={k}>{k}: {v.toFixed(3)} (Δ {optResult.deltas[k]?.toFixed(3) ?? '0.000'})</p>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="col-span-3 rounded-xl bg-slate-50 p-4">
              <h3 className="font-semibold">Relevance panel</h3>
              <p className="text-xs text-slate-500">Include/exclude compartments and rerun optimization.</p>
              <div className="mt-2 max-h-[520px] overflow-auto rounded border bg-white p-2 text-xs">
                {(availableCompartments.length ? availableCompartments : selectedCompartments).map((comp) => {
                  const score = optResult?.selected_compartments.find((c) => c.compartment === comp)?.score ?? 0
                  return (
                    <label key={comp} className="mb-1 flex items-center justify-between gap-2 border-b py-1">
                      <span>{comp} ({score.toFixed(3)})</span>
                      <input type="checkbox" checked={selectedCompartments.includes(comp)} onChange={() => toggleCompartment(comp)} />
                    </label>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {tab === 'MODELS' && (
          <div className="mt-4 rounded-xl bg-slate-50 p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-semibold">Trained models</h3>
              <button className="rounded bg-slate-700 px-3 py-1 text-white" onClick={loadRuns}>Refresh</button>
            </div>
            <table className="w-full text-left text-sm">
              <thead><tr><th>Run</th><th>Product</th><th>Created</th><th>Metrics</th><th>Active</th><th>Actions</th></tr></thead>
              <tbody>
                {registry.map((r) => (
                  <tr key={r.run_id} className="border-t align-top">
                    <td>{r.run_id}</td>
                    <td>{r.product_name}</td>
                    <td>{r.created_at}</td>
                    <td className="max-w-[260px] truncate">{JSON.stringify(r.metrics)}</td>
                    <td>{r.is_active ? '✅' : '—'}</td>
                    <td>
                      <button className="mr-2 rounded bg-indigo-600 px-2 py-1 text-white" onClick={() => activateModel(r.run_id)}>Set Active for This Product</button>
                      <button className="rounded bg-slate-700 px-2 py-1 text-white" onClick={() => downloadModelArtifact(r.run_id)}>Download Model Artifact</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
