import React from 'react'

export default function LiveLogs({ logs, progress }) {
  return (
    <div className="card full">
      <h3>Live Logs</h3>
      <div className="small mb-8">Progress: {progress}%</div>
      <div className="progress mb-8"><div className="progress-bar" style={{ width: `${progress}%` }} /></div>
      <div className="log-list">
        {logs.map((l, i) => <div key={i} className={`log ${l.level || 'info'}`}>{l.ts} — {l.message}</div>)}
      </div>
    </div>
  )
}
