import React, { useEffect, useRef } from 'react'

function formatTime(t) {
  if (!t || !isFinite(t)) return '0:00'
  const m = Math.floor(t / 60)
  const s = Math.floor(t % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function FundamentalFreqResult({ task, result }) {
  const canvasRef = useRef(null)

  const times = result.times || []
  const f0 = result.f0 || []

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !times.length) return
    const ctx = canvas.getContext('2d')
    const w = canvas.width
    const h = canvas.height
    const padding = 36

    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = '#0f1420'
    ctx.fillRect(0, 0, w, h)

    const voiced = f0.filter((v) => v)
    const loFreq = voiced.length ? Math.max(30, Math.min(...voiced) - 20) : 60
    const hiFreq = voiced.length ? Math.max(...voiced) + 20 : 500
    const duration = result.duration || times[times.length - 1] || 1

    // Grid + axis labels
    ctx.strokeStyle = '#232a3d'
    ctx.fillStyle = '#7b869f'
    ctx.font = '10px sans-serif'
    ctx.lineWidth = 0.5
    const ticks = 4
    for (let i = 0; i <= ticks; i++) {
      const freq = hiFreq - ((hiFreq - loFreq) * i) / ticks
      const y = padding + ((h - padding * 2) * i) / ticks
      ctx.beginPath()
      ctx.moveTo(padding, y)
      ctx.lineTo(w, y)
      ctx.stroke()
      ctx.fillText(`${Math.round(freq)} Hz`, 2, y + 3)
    }

    // Pitch contour line, with gaps at unvoiced (null) frames
    ctx.strokeStyle = '#818cf8'
    ctx.lineWidth = 2
    ctx.beginPath()
    let drawing = false
    times.forEach((t, i) => {
      const v = f0[i]
      const x = padding + ((w - padding) * t) / duration
      if (!v) {
        drawing = false
        return
      }
      const clamped = Math.max(loFreq, Math.min(hiFreq, v))
      const y = padding + ((h - padding * 2) * (hiFreq - clamped)) / (hiFreq - loFreq)
      if (!drawing) {
        ctx.moveTo(x, y)
        drawing = true
      } else {
        ctx.lineTo(x, y)
      }
    })
    ctx.stroke()
  }, [times, f0, result.duration])

  return (
    <div className="diarization-viz">
      <audio controls src={`/api/download/${task}`} className="diarization-audio" />

      <div className="f0-stats">
        <div className="f0-stat">
          <span className="f0-stat-label">Mean</span>
          <span className="f0-stat-value">{result.mean_f0 ? `${result.mean_f0} Hz` : '—'}</span>
        </div>
        <div className="f0-stat">
          <span className="f0-stat-label">Min</span>
          <span className="f0-stat-value">{result.min_f0 ? `${result.min_f0} Hz` : '—'}</span>
        </div>
        <div className="f0-stat">
          <span className="f0-stat-label">Max</span>
          <span className="f0-stat-value">{result.max_f0 ? `${result.max_f0} Hz` : '—'}</span>
        </div>
        <div className="f0-stat">
          <span className="f0-stat-label">Duration</span>
          <span className="f0-stat-value">{formatTime(result.duration)}</span>
        </div>
      </div>

      <div className="viz-block">
        <h3 className="viz-title">Pitch Contour (F0)</h3>
        <canvas ref={canvasRef} width={900} height={260} className="viz-canvas" />
      </div>
    </div>
  )
}
