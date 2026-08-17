import React, { useEffect, useRef } from 'react'

// Color stops for the spectrogram heatmap, low magnitude -> high magnitude.
const COLOR_STOPS = [
  [0.0, [15, 20, 32]],
  [0.35, [79, 70, 229]],
  [0.65, [219, 39, 119]],
  [0.85, [249, 115, 22]],
  [1.0, [253, 224, 71]],
]

function magnitudeColor(v) {
  for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
    const [t0, c0] = COLOR_STOPS[i]
    const [t1, c1] = COLOR_STOPS[i + 1]
    if (v >= t0 && v <= t1) {
      const t = t1 === t0 ? 0 : (v - t0) / (t1 - t0)
      return [
        Math.round(c0[0] + (c1[0] - c0[0]) * t),
        Math.round(c0[1] + (c1[1] - c0[1]) * t),
        Math.round(c0[2] + (c1[2] - c0[2]) * t),
      ]
    }
  }
  return COLOR_STOPS[COLOR_STOPS.length - 1][1]
}

function formatTime(t) {
  if (!t || !isFinite(t)) return '0:00'
  const m = Math.floor(t / 60)
  const s = Math.floor(t % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function VisualizationResult({ task, result }) {
  const waveformRef = useRef(null)
  const spectrogramRef = useRef(null)

  useEffect(() => {
    const canvas = waveformRef.current
    const peaks = result.waveform
    if (!canvas || !peaks || !peaks.length) return
    const ctx = canvas.getContext('2d')
    const w = canvas.width
    const h = canvas.height

    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = '#0f1420'
    ctx.fillRect(0, 0, w, h)

    const gradient = ctx.createLinearGradient(0, 0, w, 0)
    gradient.addColorStop(0, '#818cf8')
    gradient.addColorStop(0.5, '#a5b4fc')
    gradient.addColorStop(1, '#f472b6')
    ctx.fillStyle = gradient

    const barWidth = w / peaks.length
    peaks.forEach((p, i) => {
      const barH = Math.max(1, p * h)
      ctx.fillRect(i * barWidth, (h - barH) / 2, Math.max(1, barWidth - 0.5), barH)
    })
  }, [result.waveform])

  useEffect(() => {
    const canvas = spectrogramRef.current
    const frames = result.spectrogram
    if (!canvas || !frames || !frames.length) return
    const ctx = canvas.getContext('2d')
    const numFrames = frames.length
    const numBins = frames[0].length

    // Build a small offscreen buffer at native data resolution, then scale
    // up onto the display canvas — far cheaper than per-cell fillRect calls.
    const off = document.createElement('canvas')
    off.width = numFrames
    off.height = numBins
    const offCtx = off.getContext('2d')
    const imgData = offCtx.createImageData(numFrames, numBins)
    for (let f = 0; f < numFrames; f++) {
      for (let b = 0; b < numBins; b++) {
        const [r, g, bl] = magnitudeColor(frames[f][b])
        const y = numBins - 1 - b // low frequency at the bottom
        const idx = (y * numFrames + f) * 4
        imgData.data[idx] = r
        imgData.data[idx + 1] = g
        imgData.data[idx + 2] = bl
        imgData.data[idx + 3] = 255
      }
    }
    offCtx.putImageData(imgData, 0, 0)

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.imageSmoothingEnabled = true
    ctx.drawImage(off, 0, 0, numFrames, numBins, 0, 0, canvas.width, canvas.height)
  }, [result.spectrogram])

  return (
    <div className="diarization-viz">
      <audio controls src={`/api/download/${task}`} className="diarization-audio" />
      <div className="viz-meta">
        Duration: {formatTime(result.duration)} · Sample rate: {result.sample_rate ? `${result.sample_rate} Hz` : '—'}
      </div>
      <div className="viz-section">
        <div className="viz-block">
          <h3 className="viz-title">Waveform</h3>
          <canvas ref={waveformRef} width={900} height={200} className="viz-canvas" />
        </div>
        <div className="viz-block">
          <h3 className="viz-title">Spectrogram</h3>
          <canvas ref={spectrogramRef} width={900} height={240} className="viz-canvas" />
        </div>
      </div>
    </div>
  )
}
