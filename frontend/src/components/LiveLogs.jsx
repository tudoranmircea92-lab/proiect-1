import React from 'react'

export default function LiveLogs({ logs }) {
  return (
    <div className="card p-3 h-100">
      <h6>Live logs</h6>
      <div style={{ maxHeight: 500, overflow: 'auto' }} className="small">
        {logs.map((l, i) => <div key={i} className={l.level === 'error' ? 'text-danger' : l.level === 'success' ? 'text-success' : l.level === 'warning' ? 'text-warning' : ''}>{l.ts} {l.message}</div>)}
      </div>
    </div>
  )
}
