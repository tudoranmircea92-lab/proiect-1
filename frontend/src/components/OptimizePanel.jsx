import React from 'react'

export default function OptimizePanel({ target, setTarget }) {
  return (
    <div className="card p-3">
      <h6>Target L*, a*, b*</h6>
      <div className="row g-2">
        <div className="col"><input className="form-control" value={target.L} onChange={(e) => setTarget({ ...target, L: Number(e.target.value) })} /></div>
        <div className="col"><input className="form-control" value={target.a} onChange={(e) => setTarget({ ...target, a: Number(e.target.value) })} /></div>
        <div className="col"><input className="form-control" value={target.b} onChange={(e) => setTarget({ ...target, b: Number(e.target.value) })} /></div>
      </div>
    </div>
  )
}
