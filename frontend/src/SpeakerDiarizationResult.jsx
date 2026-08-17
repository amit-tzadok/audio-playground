import React, { useEffect, useMemo, useRef, useState } from 'react'
import GlassButton from './GlassButton'
import CircularProgress from './CircularProgress'

// Fixed-order categorical palette (colorblind-validated), assigned to
// speakers in order of first appearance — never cycled per-render.
const PALETTE = ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#4a3aa7', '#e34948', '#e87ba4', '#eb6834']

function speakerColorMap(segments) {
  const map = {}
  let i = 0
  for (const seg of segments) {
    if (!(seg.speaker in map)) {
      map[seg.speaker] = PALETTE[i % PALETTE.length]
      i++
    }
  }
  return map
}

function paceLabel(rate) {
  if (rate < 0.97) return 'slower'
  if (rate > 1.03) return 'faster'
  return 'normal'
}

export default function SpeakerDiarizationResult({ task, result }) {
  const audioRef = useRef(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  const segments = result.segments || []
  const colorMap = useMemo(() => speakerColorMap(segments), [segments])
  const speakers = Object.keys(colorMap)
  const totalDuration = duration || (segments.length ? segments[segments.length - 1].end_seconds : 0)

  const [speakerRates, setSpeakerRates] = useState({})
  useEffect(() => {
    setSpeakerRates(Object.fromEntries(speakers.map((sp) => [sp, 1.0])))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speakers.join(',')])

  const [remixTask, setRemixTask] = useState(null)
  const [remixStatus, setRemixStatus] = useState(null)
  const [remixResult, setRemixResult] = useState(null)
  const [remixing, setRemixing] = useState(false)
  const [remixStartedAt, setRemixStartedAt] = useState(null)
  const [remixElapsed, setRemixElapsed] = useState(0)

  const [instruction, setInstruction] = useState('')
  const [interpreting, setInterpreting] = useState(false)
  const [interpretExplanation, setInterpretExplanation] = useState(null)
  const [needsClarification, setNeedsClarification] = useState(false)
  const [interpretError, setInterpretError] = useState(null)

  useEffect(() => {
    let iv
    if (remixTask && remixStatus !== 'SUCCESS' && remixStatus !== 'FAILURE') {
      iv = setInterval(async () => {
        try {
          const res = await fetch(`/api/status/${remixTask}`)
          const j = await res.json()
          setRemixStatus(j.state)
          setRemixResult(j.result)
        } catch (err) {
          console.error('Remix status check failed:', err)
        }
      }, 1500)
    }
    return () => clearInterval(iv)
  }, [remixTask, remixStatus])

  useEffect(() => {
    let iv
    if (remixStartedAt && remixStatus !== 'SUCCESS' && remixStatus !== 'FAILURE') {
      iv = setInterval(() => {
        setRemixElapsed((Date.now() - remixStartedAt) / 1000)
      }, 300)
    }
    return () => clearInterval(iv)
  }, [remixStartedAt, remixStatus])

  // Remix is a fast DSP-only pass (no ML model), so ease toward a cap on
  // elapsed time alone when there's no granular current/total to report,
  // rather than leaving the ring just spinning with no sense of progress.
  function getRemixPercent() {
    if (remixStatus === 'PROGRESS' && remixResult && remixResult.total > 0) {
      return (remixResult.current / remixResult.total) * 100
    }
    const timeConstant = 3
    return Math.min(96, 100 * (1 - Math.exp(-remixElapsed / timeConstant)))
  }

  function seekTo(seconds) {
    if (audioRef.current) {
      audioRef.current.currentTime = seconds
      audioRef.current.play()
    }
  }

  async function interpretInstruction() {
    if (!instruction.trim()) return
    setInterpreting(true)
    setInterpretExplanation(null)
    setNeedsClarification(false)
    setInterpretError(null)
    try {
      const res = await fetch(`/api/interpret/${task}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instruction }),
      })
      const j = await res.json()
      if (j.error) {
        setInterpretError(j.error)
      } else if (j.needs_clarification) {
        setNeedsClarification(true)
        setInterpretExplanation(j.explanation)
      } else {
        setSpeakerRates((r) => ({ ...r, ...j.speaker_rates }))
        setInterpretExplanation(j.explanation)
      }
    } catch (err) {
      setInterpretError(err.message)
    } finally {
      setInterpreting(false)
    }
  }

  async function rebuildConversation() {
    setRemixing(true)
    setRemixTask(null)
    setRemixStatus(null)
    setRemixResult(null)
    try {
      const res = await fetch(`/api/remix/${task}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speaker_rates: speakerRates }),
      })
      const j = await res.json()
      setRemixTask(j.task_id)
      setRemixStatus('PENDING')
      setRemixStartedAt(Date.now())
      setRemixElapsed(0)
    } catch (err) {
      alert('Rebuild failed: ' + err.message)
    } finally {
      setRemixing(false)
    }
  }

  return (
    <div className="diarization-viz">
      <audio
        ref={audioRef}
        controls
        src={`/api/download/${task}`}
        className="diarization-audio"
        onTimeUpdate={(e) => setCurrentTime(e.target.currentTime)}
        onLoadedMetadata={(e) => setDuration(e.target.duration)}
      />

      {totalDuration > 0 && (
        <div className="timeline">
          <div className="timeline-track">
            {segments.map((seg, i) => {
              const active = currentTime >= seg.start_seconds && currentTime < seg.end_seconds
              const left = (seg.start_seconds / totalDuration) * 100
              const width = ((seg.end_seconds - seg.start_seconds) / totalDuration) * 100
              return (
                <div
                  key={i}
                  className={`timeline-segment ${active ? 'active' : ''}`}
                  style={{ left: `${left}%`, width: `${Math.max(width, 0.2)}%`, background: colorMap[seg.speaker] }}
                  onClick={() => seekTo(seg.start_seconds)}
                >
                  <span className="timeline-tooltip">{seg.speaker} · {seg.start} → {seg.end}</span>
                </div>
              )
            })}
            {duration > 0 && (
              <div className="timeline-playhead" style={{ left: `${(currentTime / totalDuration) * 100}%` }} />
            )}
          </div>
        </div>
      )}

      <div className="speaker-legend">
        {speakers.map((sp) => (
          <div className="legend-item" key={sp}>
            <span className="legend-swatch" style={{ background: colorMap[sp] }} />
            <span>{sp}</span>
            {result.speaker_files && result.speaker_files[sp] && (
              <a href={`/api/download/${task}/speaker/${sp}`} download className="legend-download">
                ⬇ download
              </a>
            )}
          </div>
        ))}
      </div>

      <div className="instruction-panel">
        <div className="pace-panel-title">Describe the adjustment you want</div>
        <div className="instruction-row">
          <input
            type="text"
            placeholder="e.g. this speaker talks too slow, make him faster"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && interpretInstruction()}
            className="url-input instruction-input"
          />
          <GlassButton
            variant="pill"
            onClick={interpretInstruction}
            disabled={interpreting || !instruction.trim()}
            className="instruction-button-glass"
          >
            {interpreting ? <span className="loader"></span> : 'Interpret'}
          </GlassButton>
        </div>
        {interpretExplanation && needsClarification && (
          <p className="instruction-clarification">❓ {interpretExplanation}</p>
        )}
        {interpretExplanation && !needsClarification && (
          <p className="instruction-explanation">✓ {interpretExplanation} — adjust further below or rebuild now.</p>
        )}
        {interpretError && <p className="remix-error">{interpretError}</p>}
      </div>

      <div className="pace-panel">
        <div className="pace-panel-title">Adjust speaking pace</div>
        {speakers.map((sp) => (
          <div className="pace-row" key={sp}>
            <span className="pace-speaker" style={{ color: colorMap[sp] }}>{sp}</span>
            <input
              type="range"
              min="0.5"
              max="2"
              step="0.05"
              value={speakerRates[sp] ?? 1}
              onChange={(e) => setSpeakerRates((r) => ({ ...r, [sp]: parseFloat(e.target.value) }))}
              className="pace-slider"
            />
            <span className="pace-value">{(speakerRates[sp] ?? 1).toFixed(2)}x ({paceLabel(speakerRates[sp] ?? 1)})</span>
          </div>
        ))}
        <div className="glass-cta-row">
          <GlassButton
            variant="cta"
            onClick={rebuildConversation}
            disabled={remixing || (remixTask && remixStatus !== 'SUCCESS' && remixStatus !== 'FAILURE')}
          >
            {remixing || (remixTask && remixStatus !== 'SUCCESS' && remixStatus !== 'FAILURE') ? (
              <>Rebuilding conversation... <span className="loader"></span></>
            ) : (
              '🔀 Rebuild conversation with these speeds'
            )}
          </GlassButton>
        </div>

        {remixTask && remixStatus !== 'SUCCESS' && remixStatus !== 'FAILURE' && (
          <div className="remix-progress">
            <CircularProgress percent={getRemixPercent()} size={40} strokeWidth={5} showLabel={false} />
            {remixStatus === 'PROGRESS' && remixResult && remixResult.total > 0 ? (
              <span className="remix-progress-label">
                Regenerating speech: turn {remixResult.current} of {remixResult.total}
                {' '}({Math.round((remixResult.current / remixResult.total) * 100)}%)
              </span>
            ) : (
              <span className="remix-progress-label">{remixStatus === 'STARTED' ? 'Transcribing and cloning voice…' : 'Queued…'}</span>
            )}
          </div>
        )}

        {remixStatus === 'SUCCESS' && remixResult && !remixResult.error && (
          <div className="remix-result">
            <p>Conversation rebuilt — same order and pauses, adjusted speaker pace:</p>
            <audio controls src={`/api/download/${remixTask}`} className="diarization-audio" />
            <a href={`/api/download/${remixTask}`} download className="legend-download">⬇ Download remixed conversation</a>
          </div>
        )}
        {remixStatus === 'FAILURE' || (remixResult && remixResult.error) ? (
          <p className="remix-error">Rebuild failed: {remixResult?.error || 'unknown error'}</p>
        ) : null}
      </div>

      <div className="segment-list">
        {segments.map((seg, i) => {
          const active = currentTime >= seg.start_seconds && currentTime < seg.end_seconds
          return (
            <div
              className={`segment-row ${active ? 'active' : ''}`}
              key={i}
              onClick={() => seekTo(seg.start_seconds)}
            >
              <span className="segment-speaker" style={{ color: colorMap[seg.speaker] }}>{seg.speaker}</span>
              <span className="segment-time">{seg.start} → {seg.end}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
