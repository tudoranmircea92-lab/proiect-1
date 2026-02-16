import React from 'react'

export default function DataPreview({ scan, onSkip, onUpdate }) {
  if (!scan) return <div className="card muted">Preview will appear after Scan Source.</div>
  const rows = scan.preview || []
  return (
    <div className="card mt-12">
      <h3>Preview</h3>
      <div className="small">Rows: {scan.row_count} | Columns: {scan.columns?.length || 0}</div>
      {scan.warning && (
        <div className="alert warning mt-8">
          {scan.warning}
          <div className="row gap-8 mt-8">
            <button className="btn" onClick={onSkip}>Skip</button>
            <button className="btn ghost" onClick={onUpdate}>Update file</button>
          </div>
        </div>
      )}
      {rows.length > 0 && (
        <div className="table-wrap mt-8">
          <table>
            <thead><tr>{Object.keys(rows[0]).map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{rows.map((r, i) => <tr key={i}>{Object.keys(rows[0]).map((c) => <td key={c}>{String(r[c] ?? '')}</td>)}</tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  )
}
