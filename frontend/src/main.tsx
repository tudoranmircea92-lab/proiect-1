import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import { DataPage } from './pages/DataPage'
import { TrainPage } from './pages/TrainPage'
import { PredictPage } from './pages/PredictPage'
import { OptimizePage } from './pages/OptimizePage'
import { PlasmaStabilityPage } from './pages/PlasmaStabilityPage'
import { DatasetProvider, useDataset } from './lib/datasetContext'
import { Badge, Card, Tabs } from './components/ui'

function AppShell() {
  const [tab, setTab] = useState('Data')
  const { datasetId, datasetSummary, modelTrained } = useDataset() as any

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <header className='space-y-3'>
        <h1 className="text-2xl font-semibold">Glass Coater ML Platform</h1>
        <Card className='py-3'>
          <div className='flex flex-wrap items-center gap-3 text-sm'>
            <span>Dataset:</span>
            <Badge className={datasetId ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}>{datasetId ? 'Loaded' : 'Not loaded'}</Badge>
            <span>Rows/Cols: {datasetSummary ? `${datasetSummary.rows}/${datasetSummary.columns}` : '-'}</span>
            <span>Model:</span>
            <Badge className={modelTrained ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}>{modelTrained ? 'Trained' : 'Not trained'}</Badge>
          </div>
        </Card>
      </header>

      <Tabs tabs={['Data', 'Train', 'Predict', 'Optimize', 'Plasma Stability']} active={tab} setActive={setTab} />

      {tab === 'Data' && <DataPage />}
      {tab === 'Train' && <TrainPage />}
      {tab === 'Predict' && <PredictPage />}
      {tab === 'Optimize' && <OptimizePage />}
      {tab === 'Plasma Stability' && <PlasmaStabilityPage />}
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <DatasetProvider>
      <AppShell />
    </DatasetProvider>
  </React.StrictMode>,
)
