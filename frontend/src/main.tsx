import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import './index.css'
import { DataPage } from './pages/DataPage'
import { TrainPage } from './pages/TrainPage'
import { PredictPage } from './pages/PredictPage'
import { OptimizePage } from './pages/OptimizePage'

function Shell() {
  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <header className="card flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold">Glass Coater ML Platform</h1>
          <p className="text-sm text-slate-500">Production workflow for color prediction and optimization</p>
        </div>
        <nav className="flex gap-2">
          {['data', 'train', 'predict', 'optimize'].map((p) => (
            <Link key={p} className="btn-secondary capitalize" to={`/${p}`}>{p}</Link>
          ))}
        </nav>
      </header>
      <Routes>
        <Route path="/data" element={<DataPage />} />
        <Route path="/train" element={<TrainPage />} />
        <Route path="/predict" element={<PredictPage />} />
        <Route path="/optimize" element={<OptimizePage />} />
        <Route path="*" element={<Navigate to="/data" />} />
      </Routes>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  </React.StrictMode>,
)
