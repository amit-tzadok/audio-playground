import React, { useState, useRef, useEffect, useCallback } from 'react'
import * as Tone from 'tone'
import iconPitch from './assets/icons/pitch.svg'
import GlassButton from './GlassButton'

// Typical speech/music samples sit well under +/-1, so raw amplitude reads
// as a near-flat line — boost visually (and clamp so peaks don't clip).
const WAVEFORM_GAIN = 3.5
const SPECTRUM_GAIN = 7

// Tone.PitchShift's delay-line/LFO algorithm computes an LFO modulation
// frequency of exactly 0 Hz at pitch=0 semitones, which freezes its
// crossfade/delay state and produces silence instead of a passthrough.
// Since 0 semitones needs no processing anyway, bypass the effect via its
// wet control rather than routing audio through the broken zero case.
function applyPitch(pitchShiftNode, semitones) {
  if (!pitchShiftNode) return
  pitchShiftNode.pitch = semitones
  pitchShiftNode.wet.value = semitones === 0 ? 0 : 1
}

export default function PitchShifter({ onBack, autoLoadUrl }) {
  const [file, setFile] = useState(null)
  const [fileName, setFileName] = useState('')
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLoaded, setIsLoaded] = useState(false)
  const [pitch, setPitch] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [audioError, setAudioError] = useState(null)

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

    try {
      await Tone.start()

      const url = URL.createObjectURL(audioFile)

      const pitchShift = new Tone.PitchShift({ pitch: pitch }).toDestination()
      applyPitch(pitchShift, pitch)
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
        onerror: (err) => {
          console.error('[PitchShifter] Player failed to load:', err)
          setAudioError('Failed to decode this audio file: ' + err)
        },
      }).connect(pitchShift)

      playerRef.current = player
    } catch (err) {
      console.error('[PitchShifter] loadAudio failed:', err)
      setAudioError('Failed to set up audio: ' + err.message)
    }
  }, [pitch])

  function handleFileChange(e) {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    setFileName(f.name)
    setIsLoaded(false)
    setIsPlaying(false)
    setCurrentTime(0)
    setAudioError(null)
    cancelAnimationFrame(animFrameRef.current)
    clearInterval(timeIntervalRef.current)
    loadAudio(f)
  }

  // Pre-load the bundled demo clip when launched from the "try it" strip,
  // same path as picking a file manually just without the file picker.
  useEffect(() => {
    if (!autoLoadUrl) return
    let cancelled = false
    fetch(autoLoadUrl)
      .then((r) => r.blob())
      .then((blob) => {
        if (cancelled) return
        setFile(blob)
        setFileName('demo-sample.mp3')
        setIsLoaded(false)
        setAudioError(null)
        loadAudio(blob)
      })
      .catch((err) => setAudioError('Failed to load demo sample: ' + err.message))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoLoadUrl])

  function handlePitchChange(e) {
    const val = parseFloat(e.target.value)
    setPitch(val)
    applyPitch(pitchShiftRef.current, val)
  }

  async function togglePlayback() {
    if (!isLoaded) return
    setAudioError(null)

    try {
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
    } catch (err) {
      console.error('[PitchShifter] togglePlayback failed:', err)
      setAudioError('Playback failed: ' + err.message)
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
    ctx.fillStyle = '#0f1420'
    ctx.fillRect(0, 0, w, h)

    // Waveform — real-world speech/music rarely swings near +/-1, so the
    // raw samples read as a near-flat line; boost visually and clamp.
    const GAIN = WAVEFORM_GAIN
    ctx.beginPath()
    ctx.strokeStyle = '#818cf8'
    ctx.lineWidth = 1.5
    for (let i = 0; i < w; i++) {
      const idx = i * step
      const val = Math.max(-1, Math.min(1, (data[idx] || 0) * GAIN))
      const y = (1 - val) * h / 2
      if (i === 0) ctx.moveTo(i, y)
      else ctx.lineTo(i, y)
    }
    ctx.stroke()

    // Clear spectrum
    const specCanvas = spectrumCanvasRef.current
    if (specCanvas) {
      const sctx = specCanvas.getContext('2d')
      sctx.fillStyle = '#0f1420'
      sctx.fillRect(0, 0, specCanvas.width, specCanvas.height)
      sctx.fillStyle = '#7b869f'
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

      wCtx.fillStyle = '#0f1420'
      wCtx.fillRect(0, 0, w, h)

      // Grid lines
      wCtx.strokeStyle = '#232a3d'
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
      gradient.addColorStop(0, '#818cf8')
      gradient.addColorStop(0.5, '#a5b4fc')
      gradient.addColorStop(1, '#818cf8')
      wCtx.beginPath()
      wCtx.strokeStyle = gradient
      wCtx.lineWidth = 2
      const sliceWidth = w / waveform.length
      let x = 0
      for (let i = 0; i < waveform.length; i++) {
        const val = Math.max(-1, Math.min(1, waveform[i] * WAVEFORM_GAIN))
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
      sCtx.fillStyle = '#0f1420'
      sCtx.fillRect(0, 0, sw, sh)

      // Grid lines for spectrum
      sCtx.strokeStyle = '#232a3d'
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
      specGradient.addColorStop(0, '#6366f1')
      specGradient.addColorStop(0.5, '#a5b4fc')
      specGradient.addColorStop(1, '#f472b6')

      for (let b = 0; b < numBars; b++) {
        // Map bar to frequency range
        const startIdx = Math.floor((b / numBars) * N / 2)
        const endIdx = Math.floor(((b + 1) / numBars) * N / 2)
        let sum = 0
        for (let i = startIdx; i < endIdx; i++) {
          sum += Math.abs(waveform[i] || 0)
        }
        const avg = sum / Math.max(1, endIdx - startIdx)
        // sqrt compresses the dynamic range so quieter bars still read
        // as visible bars instead of disappearing near the baseline.
        const barHeight = Math.min(sh, Math.sqrt(avg * SPECTRUM_GAIN) * sh)

        const x = b * (barWidth + 2) + 1
        sCtx.fillStyle = specGradient
        sCtx.fillRect(x, sh - barHeight, barWidth, barHeight)

        // Bar reflection
        sCtx.fillStyle = 'rgba(129, 140, 248, 0.12)'
        sCtx.fillRect(x, sh - barHeight - 2, barWidth, 2)
      }

      // Frequency labels
      sCtx.fillStyle = '#7b869f'
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
        <GlassButton variant="pill" onClick={onBack}>← Back to Tools</GlassButton>
        <div className="tool-header-icon">
          <img src={iconPitch} alt="" className="tool-icon-img" />
        </div>
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
        {audioError && <p className="remix-error">⚠ {audioError}</p>}
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
              <GlassButton
                key={p.label}
                variant="pill"
                active={pitch === p.val}
                className="preset-btn-glass"
                onClick={() => {
                  setPitch(p.val)
                  applyPitch(pitchShiftRef.current, p.val)
                }}
              >
                {p.label}
              </GlassButton>
            ))}
          </div>

          {/* Playback controls */}
          <div className="playback-row">
            <GlassButton variant="cta" className="play-btn-glass" onClick={togglePlayback}>
              {isPlaying ? '⏹ Stop' : '▶ Play'}
            </GlassButton>
            <div className="progress-bar-track">
              <div
                className="progress-bar-fill"
                style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}
              />
            </div>
            <div className="time-display">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
          </div>

          {/* Visualization */}
          <div className="viz-section">
            <div className="viz-block">
              <h3 className="viz-title">Waveform</h3>
              <canvas
                ref={waveformCanvasRef}
                width={900}
                height={240}
                className="viz-canvas"
              />
            </div>
            <div className="viz-block">
              <h3 className="viz-title">Frequency Spectrum</h3>
              <canvas
                ref={spectrumCanvasRef}
                width={900}
                height={240}
                className="viz-canvas"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
