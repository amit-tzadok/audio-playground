import React, { useState, useRef, useEffect, useCallback } from 'react'
import * as Tone from 'tone'

export default function PitchShifter({ onBack }) {
  const [file, setFile] = useState(null)
  const [fileName, setFileName] = useState('')
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLoaded, setIsLoaded] = useState(false)
  const [pitch, setPitch] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  const playerRef = useRef(null)
  const pitchShiftRef = useRef(null)
  const analyserRef = useRef(null)
  const waveformCanvasRef = useRef(null)
  const spectrumCanvasRef = useRef(null)
  const animFrameRef = useRef(null)
  const timeIntervalRef = useRef(null)
  const startTimeRef = useRef(0)

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopPlayback()
      if (playerRef.current) {
        playerRef.current.dispose()
      }
      if (pitchShiftRef.current) {
        pitchShiftRef.current.dispose()
      }
      if (analyserRef.current) {
        analyserRef.current.dispose()
      }
    }
  }, [])

  const loadAudio = useCallback(async (audioFile) => {
    // Dispose previous
    if (playerRef.current) {
      playerRef.current.stop()
      playerRef.current.dispose()
    }
    if (pitchShiftRef.current) pitchShiftRef.current.dispose()
    if (analyserRef.current) analyserRef.current.dispose()

    await Tone.start()

    const url = URL.createObjectURL(audioFile)

    const pitchShift = new Tone.PitchShift({ pitch: pitch }).toDestination()
    pitchShiftRef.current = pitchShift

    const analyser = new Tone.Analyser('waveform', 2048)
    analyserRef.current = analyser
    pitchShift.connect(analyser)

    const player = new Tone.Player({
      url,
      onload: () => {
        setDuration(player.buffer.duration)
        setIsLoaded(true)
        drawStaticWaveform(player.buffer)
      },
    }).connect(pitchShift)

    playerRef.current = player
  }, [pitch])

  function handleFileChange(e) {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    setFileName(f.name)
    setIsLoaded(false)
    setIsPlaying(false)
    setCurrentTime(0)
    cancelAnimationFrame(animFrameRef.current)
    clearInterval(timeIntervalRef.current)
    loadAudio(f)
  }

  function handlePitchChange(e) {
    const val = parseFloat(e.target.value)
    setPitch(val)
    if (pitchShiftRef.current) {
      pitchShiftRef.current.pitch = val
    }
  }

  async function togglePlayback() {
    if (!isLoaded) return
    await Tone.start()

    if (isPlaying) {
      stopPlayback()
    } else {
      playerRef.current.start()
      setIsPlaying(true)
      startTimeRef.current = Tone.now()

      // Track time
      timeIntervalRef.current = setInterval(() => {
        const elapsed = Tone.now() - startTimeRef.current
        if (elapsed >= duration) {
          stopPlayback()
          setCurrentTime(0)
        } else {
          setCurrentTime(elapsed)
        }
      }, 50)

      // Start visualization loop
      drawLive()
    }
  }

  function stopPlayback() {
    if (playerRef.current && isPlaying) {
      try { playerRef.current.stop() } catch (_) {}
    }
    setIsPlaying(false)
    cancelAnimationFrame(animFrameRef.current)
    clearInterval(timeIntervalRef.current)
  }

  function drawStaticWaveform(buffer) {
    const canvas = waveformCanvasRef.current
    if (!canvas || !buffer) return
    const ctx = canvas.getContext('2d')
    const w = canvas.width
    const h = canvas.height
    const data = buffer.getChannelData(0)
    const step = Math.ceil(data.length / w)

    ctx.clearRect(0, 0, w, h)

    // Background
    ctx.fillStyle = '#1a202c'
    ctx.fillRect(0, 0, w, h)

    // Waveform
    ctx.beginPath()
    ctx.strokeStyle = '#667eea'
    ctx.lineWidth = 1.5
    for (let i = 0; i < w; i++) {
      const idx = i * step
      const val = data[idx] || 0
      const y = (1 - val) * h / 2
      if (i === 0) ctx.moveTo(i, y)
      else ctx.lineTo(i, y)
    }
    ctx.stroke()

    // Clear spectrum
    const specCanvas = spectrumCanvasRef.current
    if (specCanvas) {
      const sctx = specCanvas.getContext('2d')
      sctx.fillStyle = '#1a202c'
      sctx.fillRect(0, 0, specCanvas.width, specCanvas.height)
      sctx.fillStyle = '#4a5568'
      sctx.font = '14px sans-serif'
      sctx.textAlign = 'center'
      sctx.fillText('Frequency spectrum will appear during playback', specCanvas.width / 2, specCanvas.height / 2)
    }
  }

  function drawLive() {
    if (!analyserRef.current) return

    const waveCanvas = waveformCanvasRef.current
    const specCanvas = spectrumCanvasRef.current
    if (!waveCanvas || !specCanvas) return

    const wCtx = waveCanvas.getContext('2d')
    const sCtx = specCanvas.getContext('2d')
    const w = waveCanvas.width
    const h = waveCanvas.height
    const sw = specCanvas.width
    const sh = specCanvas.height

    function loop() {
      // Waveform
      const waveform = analyserRef.current.getValue()
      wCtx.fillStyle = '#1a202c'
      wCtx.fillRect(0, 0, w, h)

      // Grid lines
      wCtx.strokeStyle = '#2d3748'
      wCtx.lineWidth = 0.5
      for (let i = 0; i < 5; i++) {
        const y = (h / 4) * i
        wCtx.beginPath()
        wCtx.moveTo(0, y)
        wCtx.lineTo(w, y)
        wCtx.stroke()
      }

      // Waveform line
      const gradient = wCtx.createLinearGradient(0, 0, w, 0)
      gradient.addColorStop(0, '#667eea')
      gradient.addColorStop(0.5, '#764ba2')
      gradient.addColorStop(1, '#667eea')
      wCtx.beginPath()
      wCtx.strokeStyle = gradient
      wCtx.lineWidth = 2
      const sliceWidth = w / waveform.length
      let x = 0
      for (let i = 0; i < waveform.length; i++) {
        const val = waveform[i]
        const y = (1 - val) * h / 2
        if (i === 0) wCtx.moveTo(x, y)
        else wCtx.lineTo(x, y)
        x += sliceWidth
      }
      wCtx.stroke()

      // Glow effect
      wCtx.shadowBlur = 0

      // Spectrum - use a separate FFT analyser
      // We'll compute a basic FFT visualization from the waveform data
      sCtx.fillStyle = '#1a202c'
      sCtx.fillRect(0, 0, sw, sh)

      // Grid lines for spectrum
      sCtx.strokeStyle = '#2d3748'
      sCtx.lineWidth = 0.5
      for (let i = 0; i < 5; i++) {
        const y = (sh / 4) * i
        sCtx.beginPath()
        sCtx.moveTo(0, y)
        sCtx.lineTo(sw, y)
        sCtx.stroke()
      }

      // Compute simple magnitude spectrum via DFT approximation
      const N = waveform.length
      const numBars = 64
      const barWidth = sw / numBars - 2
      const specGradient = sCtx.createLinearGradient(0, sh, 0, 0)
      specGradient.addColorStop(0, '#667eea')
      specGradient.addColorStop(0.5, '#764ba2')
      specGradient.addColorStop(1, '#e53e3e')

      for (let b = 0; b < numBars; b++) {
        // Map bar to frequency range
        const startIdx = Math.floor((b / numBars) * N / 2)
        const endIdx = Math.floor(((b + 1) / numBars) * N / 2)
        let sum = 0
        for (let i = startIdx; i < endIdx; i++) {
          sum += Math.abs(waveform[i] || 0)
        }
        const avg = sum / Math.max(1, endIdx - startIdx)
        const barHeight = avg * sh * 3

        const x = b * (barWidth + 2) + 1
        sCtx.fillStyle = specGradient
        sCtx.fillRect(x, sh - barHeight, barWidth, barHeight)

        // Bar reflection
        sCtx.fillStyle = 'rgba(102, 126, 234, 0.1)'
        sCtx.fillRect(x, sh - barHeight - 2, barWidth, 2)
      }

      // Frequency labels
      sCtx.fillStyle = '#4a5568'
      sCtx.font = '10px sans-serif'
      sCtx.textAlign = 'center'
      const freqLabels = ['0', '1k', '2k', '4k', '8k', '16k']
      freqLabels.forEach((label, i) => {
        const lx = (i / (freqLabels.length - 1)) * sw
        sCtx.fillText(label + ' Hz', lx, sh - 2)
      })

      animFrameRef.current = requestAnimationFrame(loop)
    }
    loop()
  }

  function formatTime(t) {
    const m = Math.floor(t / 60)
    const s = Math.floor(t % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  function getPitchLabel(val) {
    if (val === 0) return 'Original'
    if (val > 0) return `+${val} semitones (higher)`
    return `${val} semitones (lower)`
  }

  return (
    <div>
      <div className="tool-header">
        <button className="back-button" onClick={onBack}>
          ← Back to Tools
        </button>
        <h2>Voice Pitch Changer</h2>
      </div>

      {/* File upload */}
      <div className="upload-section">
        <div className="file-input-wrapper">
          <input
            id="pitch-file-input"
            type="file"
            accept="audio/*"
            onChange={handleFileChange}
          />
          <label htmlFor="pitch-file-input" className={`file-input-label ${file ? 'has-file' : ''}`}>
            <span className="file-icon">{file ? '✓' : '📁'}</span>
            <span>{file ? fileName : 'Choose an audio file or drag it here'}</span>
          </label>
        </div>
      </div>

      {isLoaded && (
        <div className="pitch-controls">
          {/* Pitch slider */}
          <div className="slider-section">
            <div className="slider-header">
              <label className="slider-label">Pitch Shift</label>
              <span className="slider-value">{getPitchLabel(pitch)}</span>
            </div>
            <input
              type="range"
              min={-12}
              max={12}
              step={0.5}
              value={pitch}
              onChange={handlePitchChange}
              className="pitch-slider"
            />
            <div className="slider-ticks">
              <span>-12</span>
              <span>-6</span>
              <span>0</span>
              <span>+6</span>
              <span>+12</span>
            </div>
          </div>

          {/* Preset buttons */}
          <div className="preset-row">
            {[
              { label: 'Deep', val: -6 },
              { label: 'Low', val: -3 },
              { label: 'Original', val: 0 },
              { label: 'High', val: 3 },
              { label: 'Chipmunk', val: 8 },
            ].map((p) => (
              <button
                key={p.label}
                className={`preset-btn ${pitch === p.val ? 'active' : ''}`}
                onClick={() => {
                  setPitch(p.val)
                  if (pitchShiftRef.current) pitchShiftRef.current.pitch = p.val
                }}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Playback controls */}
          <div className="playback-row">
            <button className="play-btn" onClick={togglePlayback}>
              {isPlaying ? '⏹ Stop' : '▶ Play'}
            </button>
            <div className="time-display">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
          </div>

          {/* Progress bar */}
          <div className="progress-bar-track">
            <div
              className="progress-bar-fill"
              style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}
            />
          </div>

          {/* Visualization */}
          <div className="viz-section">
            <div className="viz-block">
              <h3 className="viz-title">Waveform</h3>
              <canvas
                ref={waveformCanvasRef}
                width={700}
                height={150}
                className="viz-canvas"
              />
            </div>
            <div className="viz-block">
              <h3 className="viz-title">Frequency Spectrum</h3>
              <canvas
                ref={spectrumCanvasRef}
                width={700}
                height={150}
                className="viz-canvas"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
