import React from 'react'

export default function FileUpload({ onFiles, files, error }) {
  return (
    <div className="card p-3">
      <h5>Browse data files</h5>
      <input type="file" multiple accept=".parquet,.csv,.xlsx" className="form-control" onChange={(e) => onFiles(Array.from(e.target.files || []))} />
      {error && <div className="alert alert-danger mt-2 mb-0 py-2">{error}</div>}
      <div className="mt-2 small">{files.length ? files.map((f) => <div key={f.name}>{f.name}</div>) : 'No files selected'}</div>
    </div>
  )
}
