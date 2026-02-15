import React from 'react'

export default function TrainingMetrics({ metrics }) {
  if (!metrics) return null
  return (
    <div className="card p-3 mb-3">
      <h6>Training metrics</h6>
      <div className="d-flex gap-4 small">
        <div>MAE L*: {metrics.MAE_L?.toFixed?.(3) ?? metrics.MAE_L}</div>
        <div>MAE a*: {metrics.MAE_a?.toFixed?.(3) ?? metrics.MAE_a}</div>
        <div>MAE b*: {metrics.MAE_b?.toFixed?.(3) ?? metrics.MAE_b}</div>
        <div>ΔE: {metrics['ΔE']?.toFixed?.(3) ?? metrics['ΔE']}</div>
      </div>
    </div>
  )
}
