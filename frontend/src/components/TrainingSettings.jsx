import React from 'react'

export default function TrainingSettings({ modelType, setModelType, productName, setProductName, onTrain, canTrain, loading }) {
  return (
    <div className="card mt-12">
      <h3>Input + Config</h3>
      <label className="small">Select Product</label>
      <select className="input" value={productName} onChange={(e) => setProductName(e.target.value)}>
        <option value="GENERAL">GENERAL</option>
        <option value="PROD_A">PROD_A</option>
        <option value="PROD_B">PROD_B</option>
      </select>
      <label className="small mt-8">Model</label>
      <select className="input" value={modelType} onChange={(e) => setModelType(e.target.value)}>
        <option value="process">Process Model</option>
        <option value="control">Group by Plate (control)</option>
      </select>
      <button className="btn mt-12" onClick={onTrain} disabled={!canTrain || loading}>{loading ? 'Training…' : 'Train Model'}</button>
    </div>
  )
}
