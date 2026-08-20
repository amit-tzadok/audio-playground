import React, { useState, useEffect } from 'react'
import PitchShifter from './PitchShifter'
import SpeakerDiarizationResult from './SpeakerDiarizationResult'
import VisualizationResult from './VisualizationResult'
import TranscriptionResult from './TranscriptionResult'
import FundamentalFreqResult from './FundamentalFreqResult'
import GlassButton from './GlassButton'
import CircularProgress from './CircularProgress'
import DemoSection from './DemoSection'
import iconPitch from './assets/icons/pitch.svg'
import iconTranscribe from './assets/icons/transcribe.svg'
import iconUrl from './assets/icons/url.svg'
import iconVisualize from './assets/icons/visualize.svg'
import iconFrequency from './assets/icons/frequency.svg'
import iconDiarization from './assets/icons/diarization.svg'
import iconRemoveMusic from './assets/icons/remove-music.svg'

// Rough [low, high] multipliers of the input file's own duration, used to
// give a "time remaining" estimate while a task has no granular progress
// to report. Calibrated from one measured run (remove-music: ~96s for a
// 4m36s file, roughly 0.35x real-time) and reasoned estimates for the
// heavier pipelines that add diarization on top — these are ballpark
// figures, not a guarantee, since actual time depends on server load and
// whether ML models are already warm in memory.
// 'visualization' and 'fundamental-freq' are deliberately absent — both are
// fast numpy-only passes with no ML models involved. 'audio2text' runs a
// small Whisper model but isn't duration-scaled the same way (~9s to
// transcribe a 4.6min file, dominated by a one-time model load), so it
// doesn't get a duration-scaled estimate either.
const ESTIMATE_MULTIPLIER = {
  'remove-music': [0.25, 0.5],
  'speaker-diarization': [0.4, 0.9],
}

function formatTime(t) {
  if (!isFinite(t) || t < 0) t = 0
  const m = Math.floor(t / 60)
  const s = Math.floor(t % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

const TOOLS = [
  { id: 'pitch-shifter', name: 'Voice Pitch Changer', icon: iconPitch, desc: 'Change your voice by shifting pitch in real-time with live visualization' },
  { id: 'audio2text', name: 'Audio to Text', icon: iconTranscribe, desc: 'Transcribe speech from audio files' },
  { id: 'url2wav', name: 'URL to WAV', icon: iconUrl, desc: 'Download and convert audio from URL' },
  { id: 'visualization', name: 'Speech Visualization', icon: iconVisualize, desc: 'Visualize audio waveforms and spectrograms' },
  { id: 'fundamental-freq', name: 'Fundamental Frequency', icon: iconFrequency, desc: 'Analyze pitch and F0 contours' },
  { id: 'speaker-diarization', name: 'Speaker Diarization', icon: iconDiarization, desc: 'Detect who spoke when in an audio file' },
  { id: 'remove-music', name: 'Remove Background Music', icon: iconRemoveMusic, desc: 'Isolate speech and remove background music or noise from an audio file' },
]

export default function App() {
  const [selectedTool, setSelectedTool] = useState(null)
  const [file, setFile] = useState(null)
  const [url, setUrl] = useState('')
  const [numSpeakers, setNumSpeakers] = useState('')
  const [task, setTask] = useState(null)
  const [status, setStatus] = useState(null)
  const [result, setResult] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [fileDuration, setFileDuration] = useState(null)
  const [taskStartedAt, setTaskStartedAt] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const [demoAutoLoad, setDemoAutoLoad] = useState(false)
  const [demoLoadingTool, setDemoLoadingTool] = useState(null)
  const [inputMode, setInputMode] = useState('file')

  useEffect(() => {
    let iv
    if (task && status !== 'SUCCESS' && status !== 'FAILURE') {
      iv = setInterval(async () => {
        try {
          const res = await fetch(`/api/status/${task}`)
          const j = await res.json()
          setStatus(j.state)
          setResult(j.result)
        } catch (err) {
          console.error('Status check failed:', err)
        }
      }, 1500)
    }
    return () => clearInterval(iv)
  }, [task, status])

  useEffect(() => {
    let iv
    if (taskStartedAt && status !== 'SUCCESS' && status !== 'FAILURE') {
      iv = setInterval(() => {
        setElapsed((Date.now() - taskStartedAt) / 1000)
      }, 500)
    }
    return () => clearInterval(iv)
  }, [taskStartedAt, status])

  function handleFileSelect(e) {
    const f = e.target.files[0]
    setFile(f)
    setFileDuration(null)
    if (f) {
      const probe = new Audio()
      probe.preload = 'metadata'
      probe.onloadedmetadata = () => setFileDuration(probe.duration)
      probe.src = URL.createObjectURL(f)
    }
  }

  function getMidEstimateSeconds() {
    const mult = ESTIMATE_MULTIPLIER[selectedTool]
    if (!mult || !fileDuration) return null
    const [lo, hi] = mult
    return (fileDuration * lo + fileDuration * hi) / 2
  }

  function getEstimate() {
    const midEstimate = getMidEstimateSeconds()
    if (midEstimate === null) return null
    const remaining = midEstimate - elapsed
    if (remaining <= 5) return 'almost done…'
    return `~${formatTime(remaining)} remaining (estimate)`
  }

  // Real percent when the backend reports granular progress; otherwise a
  // percent derived from elapsed time so the ring actually fills instead
  // of just spinning — either against our duration-based estimate, or, for
  // tools with no such estimate, an easing curve that approaches (but
  // never quite reaches) 100% until the task actually finishes.
  function getPercent() {
    if (status === 'PROGRESS' && result && result.total > 0) {
      return (result.current / result.total) * 100
    }
    const midEstimate = getMidEstimateSeconds()
    if (midEstimate) {
      return Math.min(96, (elapsed / midEstimate) * 100)
    }
    const timeConstant = 6
    return Math.min(96, 100 * (1 - Math.exp(-elapsed / timeConstant)))
  }

  function usingUrlMode(tool, hasFileOverride) {
    if (hasFileOverride) return false
    return tool === 'url2wav' || inputMode === 'url'
  }

  async function processAudio(fileOverride, toolOverride) {
    const activeTool = toolOverride || selectedTool
    const activeFile = fileOverride || file
    const viaUrl = usingUrlMode(activeTool, !!fileOverride)

    if (viaUrl && !url) {
      alert('Please enter a URL')
      return
    }
    if (!viaUrl && !activeFile) {
      alert('Please select a file')
      return
    }

    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('tool', activeTool)
      if (viaUrl) {
        fd.append('url', url)
      } else {
        fd.append('file', activeFile)
      }
      if (activeTool === 'speaker-diarization' && numSpeakers) fd.append('num_speakers', numSpeakers)

      const res = await fetch('/api/upload', { method: 'POST', body: fd })
      const j = await res.json()
      setTask(j.task_id)
      setStatus('PENDING')
      setTaskStartedAt(Date.now())
      setElapsed(0)
    } catch (err) {
      alert('Processing failed: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  // Fetches the bundled demo clip and runs it straight through the real
  // pipeline for the given tool — same upload/poll/render path a manual
  // upload takes, just pre-loaded so there's nothing for the visitor to do.
  async function startDemo(toolId) {
    setDemoLoadingTool(toolId)
    try {
      if (toolId === 'pitch-shifter') {
        setSelectedTool('pitch-shifter')
        setDemoAutoLoad(true)
        return
      }
      const res = await fetch('/demo-sample.mp3')
      const blob = await res.blob()
      const demoFile = new File([blob], 'demo-sample.mp3', { type: 'audio/mpeg' })

      setSelectedTool(toolId)
      setFile(demoFile)
      setFileDuration(null)
      const probe = new Audio()
      probe.preload = 'metadata'
      probe.onloadedmetadata = () => setFileDuration(probe.duration)
      probe.src = URL.createObjectURL(demoFile)

      await processAudio(demoFile, toolId)
    } catch (err) {
      alert('Demo failed to load: ' + err.message)
    } finally {
      setDemoLoadingTool(null)
    }
  }

  function resetForm() {
    setSelectedTool(null)
    setFile(null)
    setUrl('')
    setNumSpeakers('')
    setTask(null)
    setStatus(null)
    setResult(null)
    setFileDuration(null)
    setTaskStartedAt(null)
    setElapsed(0)
    setDemoAutoLoad(false)
    setInputMode('file')
  }

  function getProcessingLabel(s, res) {
    if (s === 'PENDING') return 'Queued…'
    if (s === 'PROGRESS' && res && res.total > 0) {
      return `Processing… ${res.current} of ${res.total} (${Math.round((res.current / res.total) * 100)}%)`
    }
    return 'Processing your audio…'
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Audio Processing Platform</h1>
        <p className="subtitle">Choose a tool and process your audio files with advanced speech analysis</p>

        {!selectedTool ? (
          <>
          <DemoSection tools={TOOLS.filter((t) => t.id !== 'url2wav')} onTry={startDemo} loadingTool={demoLoadingTool} />
          <div className="tool-grid">
            {TOOLS.map(tool => (
              <div
                key={tool.id}
                className="tool-card"
                onClick={() => setSelectedTool(tool.id)}
              >
                <div className="tool-icon"><img src={tool.icon} alt="" className="tool-icon-img" /></div>
                <h3>{tool.name}</h3>
                <p>{tool.desc}</p>
              </div>
            ))}
          </div>
          </>
        ) : selectedTool === 'pitch-shifter' ? (
          <PitchShifter onBack={resetForm} autoLoadUrl={demoAutoLoad ? '/demo-sample.mp3' : null} />
        ) : (
          <>
            <div className="tool-header">
              <GlassButton variant="pill" onClick={resetForm}>← Back to Tools</GlassButton>
              <div className="tool-header-icon">
                <img src={TOOLS.find(t => t.id === selectedTool)?.icon} alt="" className="tool-icon-img" />
              </div>
              <h2>{TOOLS.find(t => t.id === selectedTool)?.name}</h2>
            </div>

            <div className="upload-section">
              {selectedTool !== 'url2wav' && (
                <div className="input-mode-toggle">
                  <button
                    type="button"
                    className={inputMode === 'file' ? 'active' : ''}
                    onClick={() => setInputMode('file')}
                  >
                    📁 Upload a file
                  </button>
                  <button
                    type="button"
                    className={inputMode === 'url' ? 'active' : ''}
                    onClick={() => setInputMode('url')}
                  >
                    🔗 Paste a YouTube URL
                  </button>
                </div>
              )}
              {selectedTool === 'url2wav' || inputMode === 'url' ? (
                <div className="url-input-wrapper">
                  <input
                    type="text"
                    placeholder="Paste a YouTube (or any yt-dlp-supported) URL"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="url-input"
                  />
                </div>
              ) : (
                <div className="file-input-wrapper">
                  <input
                    id="file-input"
                    type="file"
                    accept="audio/*"
                    onChange={handleFileSelect}
                  />
                  <label htmlFor="file-input" className={`file-input-label ${file ? 'has-file' : ''}`}>
                    <span className="file-icon">{file ? '✓' : '📁'}</span>
                    <span>{file ? file.name : 'Choose an audio file or drag it here'}</span>
                  </label>
                </div>
              )}
              {selectedTool === 'speaker-diarization' && (
                <div className="url-input-wrapper">
                  <input
                    type="number"
                    min="1"
                    placeholder="Number of speakers (optional, auto-detected if blank)"
                    value={numSpeakers}
                    onChange={(e) => setNumSpeakers(e.target.value)}
                    className="url-input"
                  />
                </div>
              )}
              <div className="glass-cta-row">
                <GlassButton
                  variant="cta"
                  onClick={processAudio}
                  disabled={(usingUrlMode(selectedTool, false) ? !url : !file) || uploading}
                >
                  {uploading ? (
                    <>
                      Processing...
                      <span className="loader"></span>
                    </>
                  ) : (
                    'Process Audio'
                  )}
                </GlassButton>
              </div>
            </div>

            {task && (
              <div className="status-panel">
                {status !== 'SUCCESS' && status !== 'FAILURE' ? (
                  <div className="task-progress">
                    <CircularProgress percent={getPercent()} />
                    <div className="task-progress-meta">
                      <span className="task-progress-label">{getProcessingLabel(status, result)}</span>
                      <span className="task-progress-time">
                        {getEstimate() || `${formatTime(elapsed)} elapsed`}
                      </span>
                    </div>
                  </div>
                ) : status === 'FAILURE' || (result && result.error) ? (
                  <p className="remix-error">⚠ Processing failed{result?.error ? `: ${result.error}` : ''}</p>
                ) : !result ? (
                  <div className="task-progress">
                    <CircularProgress percent={99} />
                    <span className="task-progress-label">Finishing up…</span>
                  </div>
                ) : (
                  <div className="status-value">
                    {selectedTool === 'url2wav' && result.path ? (
                      <a href={`/api/download/${task}`} download={result.filename}>
                        ⬇ Download {result.filename}
                      </a>
                    ) : selectedTool === 'remove-music' && result.path ? (
                      <div className="remix-result">
                        <audio controls src={`/api/download/${task}`} className="diarization-audio" />
                        <a href={`/api/download/${task}`} download={result.filename}>
                          ⬇ Download {result.filename}
                        </a>
                      </div>
                    ) : selectedTool === 'speaker-diarization' && result.segments ? (
                      <SpeakerDiarizationResult task={task} result={result} />
                    ) : selectedTool === 'visualization' && result.waveform ? (
                      <VisualizationResult task={task} result={result} />
                    ) : selectedTool === 'audio2text' && result.segments ? (
                      <TranscriptionResult task={task} result={result} />
                    ) : selectedTool === 'fundamental-freq' && result.f0 ? (
                      <FundamentalFreqResult task={task} result={result} />
                    ) : (
                      <pre>{JSON.stringify(result, null, 2)}</pre>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
