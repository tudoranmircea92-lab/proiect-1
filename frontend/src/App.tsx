import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from './api/client'
import type { OptimizeResult, RegistryRun, TrainRun } from './types'

const defaultTargets = ['L_star_RG_mean', 'a_star_RG_mean', 'b_star_RG_mean']

export default function App() {
  const [tab, setTab] = useState<'TRAIN' | 'OPTIMIZE' | 'MODELS'>('TRAIN')
  const [logs, setLogs] = useState<string[]>([])
  const [scan, setScan] = useState<any>(null)
  const [run, setRun] = useState<TrainRun | null>(null)
  const [registry, setRegistry] = useState<RegistryRun[]>([])
  const [importance, setImportance] = useState<any>(null)
  const [optResult, setOptResult] = useState<OptimizeResult | null>(null)
  const [progress, setProgress] = useState(0)

  const [trainForm, setTrainForm] = useState({ path: 'backend/app/data/sample_merged.parquet', product_name: 'PROD_A', model_type: 'process', split_mode: 'time-based', include_general_model: true })
  const [optForm, setOptForm] = useState({
    product_name: 'PROD_A', targetL: 61, targetA: 11, targetB: 9, mode: 'balanced',
    currentStateJson: '{"product_name":"PROD_A","c4.pwr":55,"c4.m1g":40,"c4.m2g":40,"c4.m3g":40,"c4.s1g":10,"c5.pwr":60,"c5.m1g":30,"c7.m2g":50,"actVacuumPressure":49}',
  })

  const log = (msg: string) => setLogs((p) => [`${new Date().toLocaleTimeString()} ${msg}`, ...p].slice(0, 40))
  const colorChartData = useMemo(() => {
    if (!optResult) return []
    return defaultTargets.map((k) => ({ target: k, before: optResult.before_color[k], after: optResult.predicted_color[k], goal: [optForm.targetL, optForm.targetA, optForm.targetB][defaultTargets.indexOf(k)] }))
  }, [optResult, optForm.targetA, optForm.targetB, optForm.targetL])

  const scanDataset = async () => {
    log('Scanning source...')
    const res = await api.post('/train/scan_source', { paths: [trainForm.path] })
    setScan(res.data)
  }

  const runTraining = async () => {
    setProgress(10)
    log('Training started')
    try {
      const res = await api.post('/train/run', {
        dataset_paths: [trainForm.path], product_name: trainForm.product_name, model_type: trainForm.model_type,
        split_mode: trainForm.split_mode, split_ratios: [0.7, 0.15, 0.15], include_general_model: trainForm.include_general_model,
        target_columns: defaultTargets, compute_delta_e: true,
      })
      setProgress(75)
      setRun(res.data)
      await loadImportance(res.data.run_id)
      await loadRuns()
      setProgress(100)
      log(`Training done: ${res.data.run_id}`)
    } catch (e: any) {
      log(`Training failed: ${e.message}`)
      setProgress(0)
    }
  }

  const loadRuns = async () => {
    const res = await api.get('/train/runs')
    setRegistry(res.data)
  }

  const activate = async (run_id: string) => {
    await api.post('/train/registry/activate', { run_id })
    log(`Activated model: ${run_id}`)
    await loadRuns()
  }

  const saveRun = async (run_id: string) => {
    const res = await api.post('/train/save', { run_id })
    log(`Saved report: ${res.data.report}`)
  }

  const loadImportance = async (runId: string) => {
    const res = await api.get(`/train/importance/${runId}`)
    setImportance(res.data)
  }

  const optimize = async () => {
    log('Optimization started')
    const res = await api.post('/optimize/run', {
      product_name: optForm.product_name,
      current_state: JSON.parse(optForm.currentStateJson),
      target_color: { L_star_RG_mean: Number(optForm.targetL), a_star_RG_mean: Number(optForm.targetA), b_star_RG_mean: Number(optForm.targetB) },
      mode: optForm.mode,
      top_k_compartments: 3,
      coverage_threshold: 0.8,
    })
    setOptResult(res.data)
    log('Optimization done')
  }

  return (
    <div className="min-h-screen bg-slate-100 p-5 text-slate-900">
      <div className="mx-auto max-w-7xl rounded-xl bg-white p-5 shadow">
        <h1 className="text-2xl font-bold">Coating Process Optimizer</h1>
        <div className="mt-3 flex gap-2">{['TRAIN', 'OPTIMIZE', 'MODELS'].map((n) => <button key={n} className={`rounded px-4 py-2 ${tab === n ? 'bg-indigo-600 text-white' : 'bg-slate-200'}`} onClick={() => setTab(n as any)}>{n}</button>)}</div>

        {tab === 'TRAIN' && <div className="mt-4 grid grid-cols-12 gap-4">
          <div className="col-span-3 rounded bg-slate-50 p-3">
            <h3 className="font-semibold">Input + Config</h3>
            <input className="mt-2 w-full rounded border p-2" value={trainForm.path} onChange={(e) => setTrainForm({ ...trainForm, path: e.target.value })} />
            <input className="mt-2 w-full rounded border p-2" value={trainForm.product_name} onChange={(e) => setTrainForm({ ...trainForm, product_name: e.target.value })} />
            <select className="mt-2 w-full rounded border p-2" value={trainForm.model_type} onChange={(e) => setTrainForm({ ...trainForm, model_type: e.target.value })}><option value="control">CONTROL MODEL</option><option value="process">PROCESS MODEL</option></select>
            <select className="mt-2 w-full rounded border p-2" value={trainForm.split_mode} onChange={(e) => setTrainForm({ ...trainForm, split_mode: e.target.value })}><option value="time-based">time-based</option><option value="group-by-plate">group-by-plate</option></select>
            <button className="mt-2 w-full rounded bg-slate-700 p-2 text-white" onClick={scanDataset}>Scan source</button>
            <button className="mt-2 w-full rounded bg-indigo-600 p-2 text-white" onClick={runTraining}>Train</button>
            <div className="mt-2 h-2 rounded bg-slate-200"><div className="h-2 rounded bg-indigo-500" style={{ width: `${progress}%` }} /></div>
          </div>
          <div className="col-span-6 rounded bg-slate-50 p-3">
            <h3 className="font-semibold">Results</h3>
            {scan && <pre className="mt-2 max-h-40 overflow-auto rounded bg-white p-2 text-xs">{JSON.stringify(scan, null, 2)}</pre>}
            {run && <pre className="mt-2 max-h-40 overflow-auto rounded bg-white p-2 text-xs">{JSON.stringify(run.metrics, null, 2)}</pre>}
            {importance && <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="h-56"><ResponsiveContainer><BarChart data={importance.by_compartment.slice(0, 8)}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="compartment"/><YAxis/><Tooltip/><Bar dataKey="importance" fill="#4f46e5"/></BarChart></ResponsiveContainer></div>
              <div className="rounded bg-white p-3 text-sm"><p>Controllable share: {(importance.share.controllable * 100).toFixed(1)}%</p><p>Context share: {(importance.share.context * 100).toFixed(1)}%</p></div>
            </div>}
          </div>
          <div className="col-span-3 rounded bg-slate-50 p-3"><h3 className="font-semibold">Live logs</h3><div className="mt-2 max-h-72 overflow-auto text-xs">{logs.map((l) => <p key={l}>{l}</p>)}</div></div>
        </div>}

        {tab === 'OPTIMIZE' && <div className="mt-4 grid grid-cols-12 gap-4">
          <div className="col-span-3 rounded bg-slate-50 p-3">
            <h3 className="font-semibold">Inputs</h3>
            <input className="mt-2 w-full rounded border p-2" value={optForm.product_name} onChange={(e) => setOptForm({ ...optForm, product_name: e.target.value })} />
            <textarea className="mt-2 h-44 w-full rounded border p-2 text-xs" value={optForm.currentStateJson} onChange={(e) => setOptForm({ ...optForm, currentStateJson: e.target.value })} />
            <div className="mt-2 grid grid-cols-3 gap-2"><input className="rounded border p-2" value={optForm.targetL} onChange={(e) => setOptForm({ ...optForm, targetL: Number(e.target.value) })}/><input className="rounded border p-2" value={optForm.targetA} onChange={(e) => setOptForm({ ...optForm, targetA: Number(e.target.value) })}/><input className="rounded border p-2" value={optForm.targetB} onChange={(e) => setOptForm({ ...optForm, targetB: Number(e.target.value) })}/></div>
            <select className="mt-2 w-full rounded border p-2" value={optForm.mode} onChange={(e) => setOptForm({ ...optForm, mode: e.target.value })}><option value="match_color">Match color</option><option value="balanced">Balanced</option><option value="minimize_gas">Minimize gas</option><option value="minimize_energy">Minimize energy</option></select>
            <button className="mt-2 w-full rounded bg-indigo-600 p-2 text-white" onClick={optimize}>Run optimization</button>
          </div>
          <div className="col-span-6 rounded bg-slate-50 p-3">
            <h3 className="font-semibold">Predicted color profile (before vs after)</h3>
            {optResult && <div className="h-64"><ResponsiveContainer><LineChart data={colorChartData}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="target"/><YAxis/><Tooltip/><Legend/><Line dataKey="before" stroke="#334155"/><Line dataKey="after" stroke="#4f46e5"/><Line dataKey="goal" stroke="#16a34a"/></LineChart></ResponsiveContainer></div>}
            {optResult && <pre className="mt-2 max-h-56 overflow-auto rounded bg-white p-2 text-xs">{JSON.stringify(optResult.selected_compartments, null, 2)}</pre>}
          </div>
          <div className="col-span-3 rounded bg-slate-50 p-3"><h3 className="font-semibold">Delta table</h3><div className="mt-2 max-h-80 overflow-auto text-xs">{optResult && Object.entries(optResult.deltas).map(([k, v]) => <p key={k}>{k}: {v.toFixed(3)}</p>)}</div></div>
        </div>}

        {tab === 'MODELS' && <div className="mt-4 rounded bg-slate-50 p-3">
          <h3 className="font-semibold">Model registry</h3>
          <button className="my-2 rounded bg-slate-700 px-3 py-1 text-white" onClick={loadRuns}>Refresh</button>
          <table className="w-full text-left text-sm"><thead><tr><th>run</th><th>product</th><th>type</th><th>active</th><th>actions</th></tr></thead><tbody>
            {registry.map((r) => <tr key={r.run_id} className="border-t"><td>{r.run_id}</td><td>{r.product_name}</td><td>{r.model_type}</td><td>{r.is_active ? '✅' : '—'}</td><td><button className="mr-2 rounded bg-indigo-600 px-2 py-1 text-white" onClick={() => activate(r.run_id)}>Set Active</button><button className="rounded bg-slate-700 px-2 py-1 text-white" onClick={() => saveRun(r.run_id)}>Export HTML report</button></td></tr>)}
          </tbody></table>
        </div>}
      </div>
    </div>
  )
}
