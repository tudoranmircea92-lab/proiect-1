import React from 'react'

export default function DataPreview({ scan, onSkip, onUpdate }) {
  if (!scan) return null
  return (
    <div className="card p-3 mt-3">
      <h6>Data preview</h6>
      <div className="small">Rows: {scan.row_count}</div>
      <div className="small">Columns: {scan.columns?.length || 0}</div>
      {scan.warning && (
        <div className="alert alert-warning py-2 mt-2">
          The dataset does not contain a 'product_name' column. You can proceed without this column or update your file to include it.
          <div className="mt-2 d-flex gap-2">
            <button className="btn btn-sm btn-primary" onClick={onSkip}>Skip</button>
            <button className="btn btn-sm btn-secondary" onClick={onUpdate}>Update file</button>
          </div>
          <div className="small mt-2">Recommended columns: 'product_name', 'date', 'plate'.</div>
        </div>
      )}
      {scan.preview?.length > 0 && (
        <>
          <div className="small fw-semibold">Showing first 5 rows of your file.</div>
          <div className="table-responsive">
            <table className="table table-sm mt-1">
              <thead><tr>{Object.keys(scan.preview[0]).map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>{scan.preview.map((r, i) => <tr key={i}>{Object.keys(scan.preview[0]).map((c) => <td key={c}>{String(r[c] ?? '')}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
