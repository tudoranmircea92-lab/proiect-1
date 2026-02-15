import React from 'react'

export default function TrainingSettings({ modelType, setModelType, productName, setProductName, onTrain, canTrain }) {
  return (
    <div className="card p-3 mt-3">
      <h6>Training settings</h6>
      <input className="form-control mb-2" value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="product_name (optional)" />
      <select className="form-select mb-2" value={modelType} onChange={(e) => setModelType(e.target.value)}>
        <option value="control">Control</option>
        <option value="process">Process</option>
      </select>
      <button className="btn btn-primary" onClick={onTrain} disabled={!canTrain}>Train</button>
    </div>
  )
}
