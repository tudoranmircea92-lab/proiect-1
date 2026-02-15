import React from 'react'

const MetricBar = ({ label, value, max = 10 }) => {
  const val = Number(value) || 0
  const pct = `${Math.min(100, (val / max) * 100)}%`
  return (
    <div className="mb-8">
      <div className="row between small"><span>{label}</span><strong>{val.toFixed(3)}</strong></div>
      <div className="progress"><div className="progress-bar alt" style={{ width: pct }} /></div>
    </div>
  )
}

export default function TrainingMetrics({ metrics }) {
  if (!metrics) return <div className="card muted">No training metrics yet.</div>
  return (
    <div className="card">
      <h3>Training Metrics</h3>
      <MetricBar label="MAE L*" value={metrics.MAE_L} />
      <MetricBar label="MAE a*" value={metrics.MAE_a} />
      <MetricBar label="MAE b*" value={metrics.MAE_b} />
      <MetricBar label="At global (ΔE)" value={metrics['ΔE']} />
    </div>
  )
}
