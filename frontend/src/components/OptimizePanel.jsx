import React from 'react'

const FIELDS = [
  'Chamber Temperature',
  'Airflow Rate',
  'Nozzle Pressure',
  'Coating Flow',
  'Humidity',
]

export default function OptimizePanel({ target, setTarget, current, setCurrent, mode, setMode, onRun, loading }) {
  return (
    <div className="card">
      <h3>Optimizer Section</h3>
      <div className="row gap-8 mb-8">
        <input className="input" type="number" value={target.L} onChange={(e) => setTarget({ ...target, L: Number(e.target.value) })} placeholder="L*" />
        <input className="input" type="number" value={target.a} onChange={(e) => setTarget({ ...target, a: Number(e.target.value) })} placeholder="a*" />
        <input className="input" type="number" value={target.b} onChange={(e) => setTarget({ ...target, b: Number(e.target.value) })} placeholder="b*" />
      </div>

      {FIELDS.map((f) => (
        <div className="mb-8" key={f}>
          <label className="small">{f}</label>
          <input className="input" type="number" value={current[f] ?? 0} onChange={(e) => setCurrent({ ...current, [f]: Number(e.target.value) })} />
        </div>
      ))}

      <label className="small">Optimization Mode</label>
      <select className="input" value={mode} onChange={(e) => setMode(e.target.value)}>
        <option value="minimize_gas">Save Gas Energy</option>
        <option value="balanced">Balanced</option>
        <option value="match_color">Match Color</option>
      </select>
      <button className="btn mt-12" onClick={onRun} disabled={loading}>{loading ? 'Optimizing…' : 'Run Optimization'}</button>
    </div>
  )
}
