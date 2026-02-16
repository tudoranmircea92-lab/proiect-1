import React, { useMemo } from 'react'

const toSvg = (rows, title) => {
  const w = 860
  const h = Math.max(220, rows.length * 24 + 70)
  const max = Math.max(...rows.map((r) => r.importance || 0), 1)
  const bars = rows.slice(0, 24).map((r, i) => {
    const y = 40 + i * 24
    const width = ((r.importance || 0) / max) * 420
    const label = (r.feature || r.compartment || 'unknown').replace(/&/g, '&amp;').replace(/</g, '&lt;')
    return `<text x="10" y="${y + 12}" font-size="11" fill="#dbe4ff">${label}</text>
      <rect x="430" y="${y}" width="${Math.max(2, width)}" height="14" rx="4" fill="#54b4d3"/>
      <text x="${435 + Math.max(2, width)}" y="${y + 11}" font-size="10" fill="#c7d2fe">${(r.importance || 0).toFixed(4)}</text>`
  }).join('\n')
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
  <rect width="100%" height="100%" fill="#0f172a"/>
  <text x="10" y="24" font-size="16" fill="#fff">${title}</text>
  ${bars}
</svg>`
}

export default function FeatureImportanceChart({ data, title = 'Feature Importance' }) {
  const rows = useMemo(() => (data || []).map((d) => ({ ...d, importance: Number(d.importance) || 0 })), [data])
  if (!rows.length) return <div className="card muted">No data available.</div>

  const max = Math.max(...rows.map((x) => x.importance), 1)

  const downloadSvg = () => {
    const svg = toSvg(rows, title)
    const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${title.toLowerCase().replace(/\s+/g, '-')}.svg`
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadPng = () => {
    const svg = toSvg(rows, title)
    const img = new Image()
    const canvas = document.createElement('canvas')
    canvas.width = 860
    canvas.height = Math.max(220, rows.length * 24 + 70)
    const ctx = canvas.getContext('2d')
    img.onload = () => {
      ctx.drawImage(img, 0, 0)
      const a = document.createElement('a')
      a.href = canvas.toDataURL('image/png')
      a.download = `${title.toLowerCase().replace(/\s+/g, '-')}.png`
      a.click()
    }
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  }

  return (
    <div className="card">
      <div className="row between center mb-8">
        <strong>{title}</strong>
        <div className="row gap-8">
          <button className="btn ghost" onClick={downloadPng}>PNG</button>
          <button className="btn ghost" onClick={downloadSvg}>SVG</button>
        </div>
      </div>
      {rows.slice(0, 24).map((x) => {
        const label = x.feature || x.compartment || 'unknown'
        const width = `${Math.max(2, (x.importance / max) * 100)}%`
        return (
          <div key={label} className="mb-8" title={`${label}: ${x.importance.toFixed(4)}`}>
            <div className="row between small"><span className="truncate">{label}</span><span>{x.importance.toFixed(4)}</span></div>
            <div className="progress"><div className="progress-bar" style={{ width }} /></div>
          </div>
        )
      })}
    </div>
  )
}
