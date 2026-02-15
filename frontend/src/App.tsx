import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from './api/client'
import type { OptimizeResult, TrainRun } from './types'

const defaultTargets = ['L_star_RG_mean', 'a_star_RG_mean', 'b_star_RG_mean']

export default function App() {
  const [tab, setTab] = useState<'TRAIN' | 'OPTIMIZE' | 'MODELS'>('TRAIN')
  const [logs, setLogs] = useState<string[]>([])
  const [training, setTraining] = useState(false)
  const [opting, setOpting] = useState(false)
  const [scan, setScan] = useState<any>(null)
  const [run, setRun] = useState<TrainRun | null>(null)
  const [registry, setRegistry] = useState<any[]>([])
  const [importance, setImportance] = useState<any>(null)
  const [optResult, setOptResult] = useState<OptimizeResult | null>(null)

  const [trainForm, setTrainForm] = useState({
    path: 'backend/app/data/sample_merged.parquet',
    product_name: 'PROD_A',
    model_type: 'process',
    split_mode: 'time-based',
    include_general_model: true,
  })

  const [optForm, setOptForm] = useState({
    product_name: 'PROD_A',
    targetL: 61,
    targetA: 11,
    targetB: 9,
    mode: 'balanced',
    currentStateJson: '{"product_name":"PROD_A","c4.pwr":55,"c4.m1g":40,"c4.m2g":40,"c4.m3g":40,"c4.s1g":10,"c5.pwr":60,"c5.m1g":30,"c7.m2g":50,"actVacuumPressure":49}',
  })

  const log = (msg: string) => setLogs((prev) => [`${new Date().toLocaleTimeString()} ${msg}`, ...prev].slice(0, 30))

  const scanDataset = async () => {
    log('Scanning datasets...')
    const res = await api.post('/train/scan', { paths: [trainForm.path] })
    setScan(res.data)
    log('Scan complete')
  }

  const runTraining = async () => {
    setTraining(true)
    try {
      log('Training started')
      const res = await api.post('/train/run', {
        dataset_paths: [trainForm.path],
        product_name: trainForm.product_name,
        model_type: trainForm.model_type,
        split_mode: trainForm.split_mode,
        split_ratios: [0.7, 0.15, 0.15],
        include_general_model: trainForm.include_general_model,
        target_columns: defaultTargets,
        compute_delta_e: true,
      })
      setRun(res.data)
      log(`Training done: ${res.data.run_id}`)
    } catch (e: any) {
      log(`Training failed: ${e.message}`)
    } finally {
      setTraining(false)
    }
  }

  const loadRegistry = async () => {
    const res = await api.get('/train/registry')
    setRegistry(res.data)
  }

  const loadImportance = async (runId: string) => {
    const res = await api.get(`/train/importance/${runId}`)
    setImportance(res.data)
  }

  const optimize = async () => {
    setOpting(true)
    try {
      log('Optimization started')
      const res = await api.post('/optimize/run', {
        product_name: optForm.product_name,
        current_state: JSON.parse(optForm.currentStateJson),
        target_color: {
          L_star_RG_mean: Number(optForm.targetL),
          a_star_RG_mean: Number(optForm.targetA),
          b_star_RG_mean: Number(optForm.targetB),
        },
        mode: optForm.mode,
        top_k_compartments: 3,
        coverage_threshold: 0.8,
      })
      setOptResult(res.data)
      log('Optimization done')
    } catch (e: any) {
      log(`Optimization failed: ${e.message}`)
    } finally {
      setOpting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 p-6 text-slate-900">
      <div className="mx-auto max-w-7xl rounded-xl bg-white p-5 shadow">
        <h1 className="text-2xl font-bold">Coating Line Optimizer</h1>
        <div className="mt-4 flex gap-2">
          {['TRAIN', 'OPTIMIZE', 'MODELS'].map((name) => (
            <button key={name} className={`rounded px-4 py-2 ${tab === name ? 'bg-indigo-600 text-white' : 'bg-slate-200'}`} onClick={() => setTab(name as any)}>{name}</button>
          ))}
        </div>

        {tab === 'TRAIN' && (
          <div className="mt-4 grid grid-cols-12 gap-4">
            <div className="col-span-3 rounded-lg bg-slate-50 p-3">
              <h2 className="mb-2 font-semibold">Inputs</h2>
              <input className="mb-2 w-full rounded border p-2" value={trainForm.path} onChange={(e) => setTrainForm({ ...trainForm, path: e.target.value })} />
              <input className="mb-2 w-full rounded border p-2" value={trainForm.product_name} onChange={(e) => setTrainForm({ ...trainForm, product_name: e.target.value })} />
              <select className="mb-2 w-full rounded border p-2" value={trainForm.model_type} onChange={(e) => setTrainForm({ ...trainForm, model_type: e.target.value })}>
                <option value="control">CONTROL MODEL</option>
                <option value="process">PROCESS MODEL</option>
              </select>
              <select className="mb-2 w-full rounded border p-2" value={trainForm.split_mode} onChange={(e) => setTrainForm({ ...trainForm, split_mode: e.target.value })}>
                <option value="time-based">time-based</option>
                <option value="group-by-plate">group-by-plate</option>
              </select>
              <button className="mb-2 w-full rounded bg-slate-700 p-2 text-white" onClick={scanDataset}>Scan dataset</button>
              <button className="w-full rounded bg-indigo-600 p-2 text-white" onClick={runTraining} disabled={training}>{training ? 'Training...' : 'Run training'}</button>
            </div>
            <div className="col-span-6 rounded-lg bg-slate-50 p-3">
              <h2 className="mb-2 font-semibold">Results</h2>
              {scan && <pre className="max-h-48 overflow-auto rounded bg-white p-2 text-xs">{JSON.stringify(scan, null, 2)}</pre>}
              {run && <pre className="mt-2 max-h-80 overflow-auto rounded bg-white p-2 text-xs">{JSON.stringify(run, null, 2)}</pre>}
              {importance && (
                <div className="mt-4 h-64">
                  <ResponsiveContainer>
                    <BarChart data={importance.by_compartment.slice(0, 10)}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="compartment" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="importance" fill="#4f46e5" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
            <div className="col-span-3 rounded-lg bg-slate-50 p-3">
              <h2 className="mb-2 font-semibold">Logs</h2>
              <button className="mb-2 rounded bg-slate-800 px-3 py-1 text-white" onClick={loadRegistry}>Load registry</button>
              {run && <button className="mb-2 ml-2 rounded bg-indigo-500 px-3 py-1 text-white" onClick={() => loadImportance(run.run_id)}>Importance</button>}
              <div className="max-h-56 overflow-auto text-xs">
                {logs.map((l) => <p key={l}>{l}</p>)}
              </div>
            </div>
          </div>
        )}

        {tab === 'OPTIMIZE' && (
          <div className="mt-4 grid grid-cols-12 gap-4">
            <div className="col-span-3 rounded-lg bg-slate-50 p-3">
              <h2 className="font-semibold">Inputs</h2>
              <input className="mb-2 mt-2 w-full rounded border p-2" value={optForm.product_name} onChange={(e) => setOptForm({ ...optForm, product_name: e.target.value })} />
              <textarea className="mb-2 h-44 w-full rounded border p-2 text-xs" value={optForm.currentStateJson} onChange={(e) => setOptForm({ ...optForm, currentStateJson: e.target.value })} />
              <div className="grid grid-cols-3 gap-2">
                <input className="rounded border p-2" value={optForm.targetL} onChange={(e) => setOptForm({ ...optForm, targetL: Number(e.target.value) })} />
                <input className="rounded border p-2" value={optForm.targetA} onChange={(e) => setOptForm({ ...optForm, targetA: Number(e.target.value) })} />
                <input className="rounded border p-2" value={optForm.targetB} onChange={(e) => setOptForm({ ...optForm, targetB: Number(e.target.value) })} />
              </div>
              <select className="my-2 w-full rounded border p-2" value={optForm.mode} onChange={(e) => setOptForm({ ...optForm, mode: e.target.value })}>
                <option value="match_color">Match color</option>
                <option value="balanced">Balanced</option>
                <option value="minimize_gas">Minimize gas</option>
                <option value="minimize_energy">Minimize energy</option>
              </select>
              <button className="w-full rounded bg-indigo-600 p-2 text-white" onClick={optimize} disabled={opting}>{opting ? 'Optimizing...' : 'Optimize'}</button>
            </div>
            <div className="col-span-6 rounded-lg bg-slate-50 p-3">
              <h2 className="font-semibold">Center: recommendation</h2>
              {optResult && <pre className="mt-2 max-h-[500px] overflow-auto rounded bg-white p-2 text-xs">{JSON.stringify(optResult, null, 2)}</pre>}
            </div>
            <div className="col-span-3 rounded-lg bg-slate-50 p-3">
              <h2 className="font-semibold">Right: deltas</h2>
              <div className="mt-2 max-h-96 overflow-auto text-xs">
                {optResult && Object.entries(optResult.deltas).map(([k, v]) => <p key={k}>{k}: {v.toFixed(3)}</p>)}
              </div>
            </div>
          </div>
        )}

        {tab === 'MODELS' && (
          <div className="mt-4 rounded-lg bg-slate-50 p-3">
            <h2 className="font-semibold">Model Registry</h2>
            <button className="my-2 rounded bg-slate-700 px-3 py-1 text-white" onClick={loadRegistry}>Refresh</button>
            <table className="w-full text-left text-sm">
              <thead><tr><th>run_id</th><th>product</th><th>type</th><th>metrics</th></tr></thead>
              <tbody>
                {registry.map((r) => (
                  <tr key={r.run_id} className="border-t"><td>{r.run_id}</td><td>{r.product_name}</td><td>{r.model_type}</td><td>{JSON.stringify(r.metrics)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
