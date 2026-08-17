import React, { useRef, useState } from 'react'

export default function TranscriptionResult({ task, result }) {
  const audioRef = useRef(null)
  const [currentTime, setCurrentTime] = useState(0)

  const segments = result.segments || []

  function seekTo(seconds) {
    if (audioRef.current) {
      audioRef.current.currentTime = seconds
      audioRef.current.play()
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
      />

      <div className="viz-meta">
        Detected language: <strong>{result.language || 'unknown'}</strong>
      </div>

      {result.text && (
        <div className="transcript-full-text">{result.text}</div>
      )}

      <div className="segment-list">
        {segments.map((seg, i) => {
          const active = currentTime >= seg.start && currentTime < seg.end
          return (
            <div
              className={`segment-row transcript-row ${active ? 'active' : ''}`}
              key={i}
              onClick={() => seekTo(seg.start)}
            >
              <span className="segment-time">{seg.start.toFixed(1)}s</span>
              <span className="transcript-row-text">{seg.text}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
