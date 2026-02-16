import React from 'react'

export default function FileUpload({ onFiles, files, error, productFilter, setProductFilter }) {
  return (
    <div className="card">
      <h3>Browse Data Files</h3>
      <input type="file" multiple accept=".parquet,.csv,.xlsx" className="input" onChange={(e) => onFiles(Array.from(e.target.files || []))} />
      <input className="input mt-8" placeholder="Filter files by product text" value={productFilter} onChange={(e) => setProductFilter(e.target.value)} />
      {error && <div className="alert danger mt-8">{error}</div>}
      <div className="small mt-8">
        {files.length ? files.map((f) => <div key={f.name}>{f.name}</div>) : 'No files selected'}
      </div>
    </div>
  )
}
