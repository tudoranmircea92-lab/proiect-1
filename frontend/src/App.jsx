import React, { useMemo, useState } from 'react'
import DataPreview from './components/DataPreview'
import FeatureImportanceChart from './components/FeatureImportanceChart'
import FileUpload from './components/FileUpload'
import LiveLogs from './components/LiveLogs'
import OptimizePanel from './components/OptimizePanel'
import TrainingMetrics from './components/TrainingMetrics'
import TrainingSettings from './components/TrainingSettings'
import { downloadArtifactUrl, getImportance, getModelHistory, optimize, saveRun, scanData, trainModel } from './services/api'

export default function App() {
  const [tab, setTab] = useState('TRAIN')
  const [theme, setTheme] = useState('dark')

  const [files, setFiles] = useState([])
  const [productFilter, setProductFilter] = useState('')
  const [scan, setScan] = useState(null)
  const [error, setError] = useState('')
  const [logs, setLogs] = useState([])
  const [progress, setProgress] = useState(0)

  const [allowMissing, setAllowMissing] = useState(false)
  const [modelType, setModelType] = useState('process')
  const [productName, setProductName] = useState('GENERAL')
  const [training, setTraining] = useState(null)
  const [view, setView] = useState('all')
  const [isScanning, setIsScanning] = useState(false)
  const [isTraining, setIsTraining] = useState(false)

  const [target, setTarget] = useState({ L: 75, a: 0.5, b: 1.0 })
  const [mode, setMode] = useState('balanced')
  const [currentState, setCurrentState] = useState({
    'Chamber Temperature': 120,
    'Airflow Rate': 38,
    'Nozzle Pressure': 4.5,
    'Coating Flow': 22,
    Humidity: 48,
  })
  const [optimizationResult, setOptimizationResult] = useState(null)
  const [isOptimizing, setIsOptimizing] = useState(false)

  const [modelHistory, setModelHistory] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  const addLog = (message, level = 'info') => setLogs((p) => [{ ts: new Date().toLocaleTimeString(), message, level }, ...p])

  const onFiles = (f) => {
    const valid = f.filter((x) => /\.(parquet|csv|xlsx)$/i.test(x.name))
    const invalid = f.length !== valid.length
    if (invalid) {
      setError('Only .parquet / .csv / .xlsx files are allowed.')
      addLog('Invalid file type filtered out', 'warning')
    } else {
      setError('')
    }
    const filtered = productFilter ? valid.filter((x) => x.name.toLowerCase().includes(productFilter.toLowerCase())) : valid
    setFiles(filtered)
  }

  const doScan = async () => {
    setIsScanning(true)
    setProgress(15)
    addLog('Scanning source files...')
    try {
      const data = await scanData(files)
      setScan(data)
      if (data.warning) addLog(data.warning, 'warning')
      setProgress(40)
      addLog('Scan complete', 'success')
    } catch (e) {
      addLog(e?.response?.data?.detail || 'Scan failed', 'error')
    } finally {
      setIsScanning(false)
    }
  }

  const doTrain = async () => {
    if (scan?.warning && !allowMissing) return addLog('Choose Skip before training without product_name.', 'warning')
    setIsTraining(true)
    setProgress(55)
    addLog('Training started...')
    const payload = {
      dataset_paths: scan?.resolved_paths || [],
      model_type: modelType,
      product_name: productName,
      target_columns: ['L_star_RG_mean', 'a_star_RG_mean', 'b_star_RG_mean'],
    }
    try {
      const out = await trainModel(payload)
      const imp = await getImportance(out.model_id)
      setTraining({ ...out, ...imp })
      addLog('Feature Importance Calculated', 'success')
      addLog('Training complete', 'success')
      setProgress(100)
    } catch (e) {
      addLog(e?.response?.data?.detail || 'Training failed', 'error')
    } finally {
      setIsTraining(false)
    }
  }

  const doOptimize = async () => {
    setIsOptimizing(true)
    setProgress(70)
    addLog('Optimization started...')
    try {
      const payload = {
        product_name: productName,
        current_state: currentState,
        target_color: target,
        mode,
      }
      const out = await optimize(payload)
      setOptimizationResult(out)
      addLog('Optimization ended', 'success')
      setProgress(100)
    } catch (e) {
      addLog(e?.response?.data?.detail || 'Optimization failed', 'error')
    } finally {
      setIsOptimizing(false)
    }
  }

  const loadModels = async () => {
    setLoadingHistory(true)
    try {
      const rows = await getModelHistory()
      setModelHistory(rows)
      addLog(`Loaded ${rows.length} model runs`, 'success')
    } catch (e) {
      addLog(e?.response?.data?.detail || 'Could not load model history', 'error')
    } finally {
      setLoadingHistory(false)
    }
  }

  const saveModelRun = async (runId) => {
    try {
      await saveRun(runId)
      addLog(`Run ${runId} saved`, 'success')
    } catch (e) {
      addLog(e?.response?.data?.detail || `Could not save run ${runId}`, 'error')
    }
  }

  const filteredImportance = useMemo(() => {
    const data = training?.feature_importances || []
    if (view === 'all') return data
    return data.filter((x) => x.group === view)
  }, [training, view])

  const optimizationChartData = useMemo(() => {
    const deltas = optimizationResult?.deltas || {}
    return Object.keys(deltas).map((k) => ({ feature: k, importance: Math.abs(Number(deltas[k]) || 0) }))
  }, [optimizationResult])

  return (
    <div className={`app ${theme}`}>
      <header className="row between center mb-12">
        <h1>Coating Process Optimizer</h1>
        <button className="btn ghost" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? 'Light' : 'Dark'} mode</button>
      </header>

      <div className="tabs mb-12">
        {['TRAIN', 'OPTIMIZE', 'MODELS'].map((t) => <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>)}
      </div>

      {tab === 'TRAIN' && (
        <div className="layout-3">
          <aside>
            <FileUpload onFiles={onFiles} files={files} error={error} productFilter={productFilter} setProductFilter={setProductFilter} />
            <button className="btn mt-12" onClick={doScan} disabled={!files.length || isScanning}>{isScanning ? 'Scanning…' : 'Scan Source'}</button>
            <DataPreview scan={scan} onSkip={() => setAllowMissing(true)} onUpdate={() => { setAllowMissing(false); setScan(null); setFiles([]) }} />
            <TrainingSettings modelType={modelType} setModelType={setModelType} productName={productName} setProductName={setProductName} onTrain={doTrain} canTrain={!!scan} loading={isTraining} />
          </aside>

          <main>
            <TrainingMetrics metrics={training?.training_metrics} />
            <div className="card mt-12">
              <div className="row between center mb-8">
                <h3>Feature Importance</h3>
                <div className="row gap-8">
                  {['all', 'controllable', 'context'].map((v) => <button key={v} className={`btn ${view === v ? '' : 'ghost'}`} onClick={() => setView(v)}>{v}</button>)}
                </div>
              </div>
              <FeatureImportanceChart data={filteredImportance.slice(0, 24)} title="Feature Importance" />
            </div>
            <div className="card mt-12">
              <h3>Importance by Compartment</h3>
              <FeatureImportanceChart data={training?.importance_by_compartment || []} title="Compartment Importance" />
              <div className="small mt-8">Controllable: {((training?.total_controllable_share || 0) * 100).toFixed(1)}% | Contextual: {((training?.total_context_share || 0) * 100).toFixed(1)}%</div>
            </div>
          </main>

          <aside>
            <LiveLogs logs={logs} progress={progress} />
          </aside>
        </div>
      )}

      {tab === 'OPTIMIZE' && (
        <div className="layout-3">
          <aside>
            <OptimizePanel
              target={target}
              setTarget={setTarget}
              current={currentState}
              setCurrent={setCurrentState}
              mode={mode}
              setMode={setMode}
              onRun={doOptimize}
              loading={isOptimizing}
            />
          </aside>
          <main>
            <div className="card">
              <h3>Coating Profiler</h3>
              <FeatureImportanceChart data={optimizationChartData} title="Optimization deltas" />
              {optimizationResult && <pre className="small pre">{JSON.stringify(optimizationResult.predicted_color, null, 2)}</pre>}
            </div>
          </main>
          <aside><LiveLogs logs={logs} progress={progress} /></aside>
        </div>
      )}

      {tab === 'MODELS' && (
        <div className="card">
          <div className="row between center mb-12">
            <h3>Model Management</h3>
            <button className="btn" onClick={loadModels} disabled={loadingHistory}>{loadingHistory ? 'Loading…' : 'Refresh History'}</button>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Run</th><th>Product</th><th>Model</th><th>Created</th><th>Metrics</th><th>Actions</th></tr></thead>
              <tbody>
                {modelHistory.map((m) => (
                  <tr key={m.run_id}>
                    <td>{m.run_id}</td>
                    <td>{m.product_name}</td>
                    <td>{m.model_type}</td>
                    <td>{m.created_at}</td>
                    <td className="small">{JSON.stringify(m.metrics || {})}</td>
                    <td>
                      <div className="row gap-8">
                        <button className="btn ghost" onClick={() => saveModelRun(m.run_id)}>Save</button>
                        <a className="btn ghost" href={downloadArtifactUrl(m.run_id)}>Download</a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
