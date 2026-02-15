import React from 'react'

const PHYSICAL_OPTIONS = [
  'Chamber Temperature',
  'Airflow Rate',
  'Nozzle Pressure',
  'Coating Flow',
  'Humidity',
]

const COLOR_OPTIONS = ['L_star_RG_mean', 'a_star_RG_mean', 'b_star_RG_mean']

const updateArray = (arr, value, checked) => {
  const s = new Set(arr || [])
  if (checked) s.add(value)
  else s.delete(value)
  return Array.from(s)
}

export default function TrainingSettings({ config, setConfig, onTrain, canTrain, loading }) {
  return (
    <div className="card mt-12">
      <h3>Advanced Training Config</h3>

      <div className="grid-2 gap-8">
        <div>
          <label className="small">Product</label>
          <select className="input" value={config.productName} onChange={(e) => setConfig({ ...config, productName: e.target.value })}>
            <option value="GENERAL">GENERAL</option>
            <option value="PROD_A">PROD_A</option>
            <option value="PROD_B">PROD_B</option>
          </select>
        </div>
        <div>
          <label className="small">Model Type</label>
          <select className="input" value={config.modelType} onChange={(e) => setConfig({ ...config, modelType: e.target.value })}>
            <option value="process">Process Model</option>
            <option value="control">Control-only Model</option>
          </select>
        </div>
      </div>

      <label className="small mt-8">Input scope</label>
      <select className="input" value={config.inputScope} onChange={(e) => setConfig({ ...config, inputScope: e.target.value })}>
        <option value="all_devices">All devices</option>
        <option value="selected_physical">Selected physical params</option>
      </select>

      <div className="mt-8">
        <div className="small">Physical params</div>
        <div className="grid-2">
          {PHYSICAL_OPTIONS.map((p) => (
            <label key={p} className="small">
              <input
                type="checkbox"
                checked={(config.physicalParams || []).includes(p)}
                onChange={(e) => setConfig({ ...config, physicalParams: updateArray(config.physicalParams, p, e.target.checked) })}
              />{' '}
              {p}
            </label>
          ))}
        </div>
      </div>

      <label className="small mt-8">Color scope</label>
      <select className="input" value={config.colorScope} onChange={(e) => setConfig({ ...config, colorScope: e.target.value })}>
        <option value="all">All colors (L*, a*, b*)</option>
        <option value="subset">Subset color</option>
      </select>
      {config.colorScope === 'subset' && (
        <select className="input mt-8" value={config.selectedColorTarget} onChange={(e) => setConfig({ ...config, selectedColorTarget: e.target.value })}>
          {COLOR_OPTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      )}

      <label className="small mt-8">Training method</label>
      <select className="input" value={config.trainingMethod} onChange={(e) => setConfig({ ...config, trainingMethod: e.target.value })}>
        <option value="all_data">All data</option>
        <option value="subset_recent">Subset recent data</option>
        <option value="per_product">Per product</option>
        <option value="filtered">Filtered by period</option>
      </select>
      {(config.trainingMethod === 'subset_recent') && (
        <input className="input mt-8" type="number" step="0.05" min="0.05" max="1" value={config.subsetRatio} onChange={(e) => setConfig({ ...config, subsetRatio: Number(e.target.value) })} placeholder="subset ratio" />
      )}
      {(config.trainingMethod === 'filtered') && (
        <div className="grid-2 gap-8 mt-8">
          <input className="input" type="date" value={config.dateFrom} onChange={(e) => setConfig({ ...config, dateFrom: e.target.value })} />
          <input className="input" type="date" value={config.dateTo} onChange={(e) => setConfig({ ...config, dateTo: e.target.value })} />
        </div>
      )}

      <label className="small mt-8">Optimizable params</label>
      <select className="input" value={config.optimizableScope} onChange={(e) => setConfig({ ...config, optimizableScope: e.target.value })}>
        <option value="controllable_only">Only controllable</option>
        <option value="all">All params</option>
      </select>
      <input
        className="input mt-8"
        placeholder="Manual overrides (JSON), ex: {\"c1.pwr\":55}"
        value={config.manualOverridesText}
        onChange={(e) => setConfig({ ...config, manualOverridesText: e.target.value })}
      />

      <label className="small mt-8">Metric mode</label>
      <select className="input" value={config.metricMode} onChange={(e) => setConfig({ ...config, metricMode: e.target.value })}>
        <option value="mae">MAE</option>
        <option value="rmse">RMSE</option>
        <option value="combined">Combined</option>
      </select>
      <input className="input mt-8" placeholder="Metric subset product (optional)" value={config.metricSubsetProduct} onChange={(e) => setConfig({ ...config, metricSubsetProduct: e.target.value })} />

      <label className="small mt-8">Model family</label>
      <select className="input" value={config.modelFamily} onChange={(e) => setConfig({ ...config, modelFamily: e.target.value })}>
        <option value="random_forest">Random Forest</option>
        <option value="neural_network">Neural Network</option>
      </select>
      <select className="input mt-8" value={config.trainingSpeed} onChange={(e) => setConfig({ ...config, trainingSpeed: e.target.value })}>
        <option value="quick">Quick</option>
        <option value="detailed">Detailed</option>
      </select>

      <label className="small mt-8">
        <input type="checkbox" checked={config.crossValidation} onChange={(e) => setConfig({ ...config, crossValidation: e.target.checked })} /> Enable cross-validation
      </label>
      {config.crossValidation && (
        <input className="input mt-8" type="number" min="2" max="8" value={config.cvFolds} onChange={(e) => setConfig({ ...config, cvFolds: Number(e.target.value) })} />
      )}

      <button className="btn mt-12" onClick={onTrain} disabled={!canTrain || loading}>{loading ? 'Training…' : 'Train Model'}</button>
    </div>
  )
}
