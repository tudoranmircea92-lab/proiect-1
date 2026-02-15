import React from 'react'

export default function FeatureImportanceChart({ data, title = 'Feature Importance' }) {
  if (!data?.length) return null

  const max = Math.max(...data.map((x) => Number(x.importance) || 0), 1)

  return (
    <div>
      <div className="small text-muted mb-2">{title}</div>
      <div>
        {data.map((x) => {
          const label = x.feature || x.compartment || 'unknown'
          const value = Number(x.importance) || 0
          const width = `${Math.max(1, (value / max) * 100)}%`
          return (
            <div key={label} className="mb-2">
              <div className="d-flex justify-content-between small">
                <span className="text-truncate" style={{ maxWidth: '70%' }}>{label}</span>
                <span>{value.toFixed(4)}</span>
              </div>
              <div className="progress" style={{ height: 10 }}>
                <div className="progress-bar bg-info" role="progressbar" style={{ width }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
