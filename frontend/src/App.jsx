import React, { useMemo, useRef, useState } from 'react'
import DataPreview from './components/DataPreview'
import FeatureImportanceChart from './components/FeatureImportanceChart'
import FileUpload from './components/FileUpload'
import LiveLogs from './components/LiveLogs'
import OptimizePanel from './components/OptimizePanel'
import TrainingMetrics from './components/TrainingMetrics'
import TrainingSettings from './components/TrainingSettings'
import { getImportance, scanData, trainModel } from './services/api'

export default function App() {
  const [tab, setTab] = useState('TRAIN')
  const [files, setFiles] = useState([])
  const [scan, setScan] = useState(null)
  const [error, setError] = useState('')
  const [logs, setLogs] = useState([])
  const [allowMissing, setAllowMissing] = useState(false)
  const [modelType, setModelType] = useState('process')
  const [productName, setProductName] = useState('GENERAL')
  const [training, setTraining] = useState(null)
  const [view, setView] = useState('all')
  const [target, setTarget] = useState({ L: 75, a: 0.5, b: 1.0 })

  const addLog = (message, level = 'info') => setLogs((p) => [{ ts: new Date().toLocaleTimeString(), message, level }, ...p])

  const onFiles = (f) => {
    const invalid = f.some((x) => !/\.(parquet|csv|xlsx)$/i.test(x.name))
    if (invalid) {
      setError('Invalid file type selected. Please upload a .csv, .xlsx, or .parquet file.')
      addLog('Invalid file type selected', 'error')
    } else {
      setError('')
    }
    setFiles(f.filter((x) => /\.(parquet|csv|xlsx)$/i.test(x.name)))
  }

  const doScan = async () => {
    addLog('Scanning data')
    try {
      const data = await scanData(files)
      setScan(data)
      if (data.warning) addLog("Warning: Dataset missing 'product_name' column. Proceeding without it.", 'warning')
      addLog('Scan successful', 'success')
    } catch (e) {
      addLog(e?.response?.data?.detail || 'Network Error', 'error')
    }
  }

  const doTrain = async () => {
    if (scan?.warning && !allowMissing) return addLog('Choose Skip or Update file for missing product_name', 'warning')
    addLog('Training model')
    const payload = { dataset_paths: scan?.resolved_paths || [], model_type: modelType, product_name: productName, target_columns: ['L_star_RG_mean', 'a_star_RG_mean', 'b_star_RG_mean'] }
    try {
      const out = await trainModel(payload)
      const imp = await getImportance(out.model_id)
      setTraining({ ...out, ...imp })
      addLog('Training complete', 'success')
    } catch (e) {
      addLog(e?.response?.data?.detail || 'Training failed', 'error')
    }
  }

  const filtered = useMemo(() => {
    const data = training?.feature_importances || []
    if (view === 'all') return data
    if (view === 'controllable') return data.filter((x) => x.group === 'controllable')
    return data.filter((x) => x.group === 'context')
  }, [training, view])

  return (
    <div className="container-fluid p-4" style={{ background: '#f3f6fb', minHeight: '100vh' }}>
      <h2 className="fw-bold mb-3">Coating Process Optimizer</h2>
      <div className="btn-group mb-3">
        {['TRAIN', 'OPTIMIZE', 'MODELS'].map((t) => <button key={t} className={`btn ${tab === t ? 'btn-primary' : 'btn-light'}`} onClick={() => setTab(t)}>{t}</button>)}
      </div>

      {tab === 'TRAIN' && (
        <div className="row g-3">
          <div className="col-md-3">
            <FileUpload onFiles={onFiles} files={files} error={error} />
            <button className="btn btn-dark w-100 mt-2" onClick={doScan}>Scan source</button>
            <DataPreview scan={scan} onSkip={() => setAllowMissing(true)} onUpdate={() => { setAllowMissing(false); setScan(null); setFiles([]) }} />
            <TrainingSettings modelType={modelType} setModelType={setModelType} productName={productName} setProductName={setProductName} onTrain={doTrain} canTrain={!!scan} />
          </div>
          <div className="col-md-6">
            <TrainingMetrics metrics={training?.training_metrics} />
            <div className="card p-3 mb-3">
              <div className="d-flex justify-content-between align-items-center mb-2">
                <h6 className="m-0">Feature importance</h6>
                <div className="btn-group btn-group-sm">
                  <button className={`btn ${view === 'all' ? 'btn-primary' : 'btn-outline-secondary'}`} onClick={() => setView('all')}>All</button>
                  <button className={`btn ${view === 'controllable' ? 'btn-primary' : 'btn-outline-secondary'}`} onClick={() => setView('controllable')}>Controllable</button>
                  <button className={`btn ${view === 'context' ? 'btn-primary' : 'btn-outline-secondary'}`} onClick={() => setView('context')}>Context</button>
                </div>
              </div>
              <FeatureImportanceChart data={filtered.slice(0, 20)} title="Feature Importance" />
            </div>
            <div className="card p-3 mb-3">
              <h6>Importance by compartment</h6>
              <FeatureImportanceChart data={training?.importance_by_compartment || []} title="Compartment Importance" />
              <div className="small mt-2">controllable: {((training?.total_controllable_share || 0) * 100).toFixed(1)}% | context: {((training?.total_context_share || 0) * 100).toFixed(1)}%</div>
            </div>
          </div>
          <div className="col-md-3"><LiveLogs logs={logs} /></div>
        </div>
      )}

      {tab === 'OPTIMIZE' && (
        <div className="row g-3">
          <div className="col-md-3"><OptimizePanel target={target} setTarget={setTarget} /></div>
          <div className="col-md-6"><div className="card p-3">Optimization panel placeholder (integrated with backend /api/optimize/run)</div></div>
          <div className="col-md-3"><LiveLogs logs={logs} /></div>
        </div>
      )}
    </div>
  )
}
