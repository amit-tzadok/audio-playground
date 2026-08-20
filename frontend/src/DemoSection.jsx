import React, { useEffect, useRef, useState } from 'react'
import GlassButton from './GlassButton'

const DEMO_URL = '/demo-sample.mp3'
const TARGET_PEAKS = 220

export default function DemoSection({ tools, onTry, loadingTool }) {
  const audioRef = useRef(null)
  const canvasRef = useRef(null)
  const [peaks, setPeaks] = useState(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  // Decode the bundled sample once on mount to get real waveform peaks —
  // this is an honest visualization of actual audio, not a fake animation.
  useEffect(() => {
    let cancelled = false
    fetch(DEMO_URL)
      .then((r) => r.arrayBuffer())
      .then((buf) => {
        const Ctx = window.AudioContext || window.webkitAudioContext
        const ctx = new Ctx()
        return ctx.decodeAudioData(buf).finally(() => ctx.close())
      })
      .then((audioBuffer) => {
        if (cancelled) return
        const data = audioBuffer.getChannelData(0)
        const step = Math.max(1, Math.ceil(data.length / TARGET_PEAKS))
        const p = []
        for (let i = 0; i < data.length; i += step) {
          let max = 0
          for (let j = i; j < Math.min(i + step, data.length); j++) {
            max = Math.max(max, Math.abs(data[j]))
          }
          p.push(max)
        }
        setPeaks(p)
      })
      .catch(() => setPeaks([]))
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !peaks || !peaks.length) return
    const ctx = canvas.getContext('2d')
    const w = canvas.width
    const h = canvas.height
    const progress = duration ? currentTime / duration : 0

    ctx.clearRect(0, 0, w, h)
    const barWidth = w / peaks.length
    peaks.forEach((p, i) => {
      const barH = Math.max(2, p * h * 3.4)
      const x = i * barWidth
      const played = i / peaks.length < progress
      ctx.fillStyle = played ? '#0d9488' : 'rgba(13, 148, 136, 0.25)'
      ctx.fillRect(x, (h - barH) / 2, Math.max(1, barWidth - 1), barH)
    })
  }, [peaks, currentTime, duration])

  function togglePlay() {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) {
      audio.pause()
    } else {
      audio.currentTime = audio.ended || audio.currentTime >= audio.duration - 0.05 ? 0 : audio.currentTime
      audio.play()
    }
  }

  return (
    <div className="demo-section">
      <div className="demo-section-head">
        <h2 className="demo-section-title">Live Demo</h2>
        <p className="demo-section-desc">No file of your own yet? Use this sample clip to try any tool right now — nothing to upload.</p>
      </div>

      <div className="demo-block">
        <span className="demo-block-label">1 · Hear the sample</span>
        <div className="demo-player">
          <GlassButton variant="pill" onClick={togglePlay}>
            {isPlaying ? '⏹ Stop' : '▶ Play sample'}
          </GlassButton>
          <canvas ref={canvasRef} width={640} height={56} className="demo-canvas" />
        </div>
        <audio
          ref={audioRef}
          src={DEMO_URL}
          preload="metadata"
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
          onTimeUpdate={(e) => setCurrentTime(e.target.currentTime)}
          onLoadedMetadata={(e) => setDuration(e.target.duration)}
        />
      </div>

      <div className="demo-block demo-block-last">
        <span className="demo-block-label">2 · Pick a tool to run on it</span>
        <div className="demo-try-row">
          {tools.map((tool) => (
            <button
              key={tool.id}
              type="button"
              className="demo-try-chip"
              onClick={() => onTry(tool.id)}
              disabled={loadingTool === tool.id}
            >
              <img src={tool.icon} alt="" className="demo-try-chip-icon" />
              <span>{loadingTool === tool.id ? 'Loading…' : tool.name}</span>
              <span className="demo-try-chip-arrow" aria-hidden="true">→</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
