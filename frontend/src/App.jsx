import React, { useState, useEffect } from 'react'
import PitchShifter from './PitchShifter'

const TOOLS = [
  { id: 'pitch-shifter', name: '🎛 Voice Pitch Changer', desc: 'Change your voice by shifting pitch in real-time with live visualization' },
  { id: 'audio2text', name: '🎤 Audio to Text', desc: 'Transcribe speech from audio files' },
  { id: 'url2wav', name: '🔗 URL to WAV', desc: 'Download and convert audio from URL' },
  { id: 'visualization', name: '📊 Speech Visualization', desc: 'Visualize audio waveforms and spectrograms' },
  { id: 'fundamental-freq', name: '🎵 Fundamental Frequency', desc: 'Analyze pitch and F0 contours' },
]

export default function App() {
  const [selectedTool, setSelectedTool] = useState(null)
  const [file, setFile] = useState(null)
  const [url, setUrl] = useState('')
  const [task, setTask] = useState(null)
  const [status, setStatus] = useState(null)
  const [result, setResult] = useState(null)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    let iv
    if (task && status !== 'SUCCESS' && status !== 'FAILURE') {
      iv = setInterval(async () => {
        try {
          const res = await fetch(`http://localhost:8000/status/${task}`)
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

  async function processAudio() {
    if (selectedTool === 'url2wav' && !url) {
      alert('Please enter a URL')
      return
    }
    if (selectedTool !== 'url2wav' && !file) {
      alert('Please select a file')
      return
    }
    
    setUploading(true)
    try {
      const fd = new FormData()
      if (file) fd.append('file', file)
      fd.append('tool', selectedTool)
      if (url) fd.append('url', url)
      
      const res = await fetch('http://localhost:8000/upload', { method: 'POST', body: fd })
      const j = await res.json()
      setTask(j.task_id)
      setStatus('PENDING')
    } catch (err) {
      alert('Processing failed: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  function resetForm() {
    setSelectedTool(null)
    setFile(null)
    setUrl('')
    setTask(null)
    setStatus(null)
    setResult(null)
  }

  function getStatusBadgeClass(s) {
    if (!s) return 'pending'
    if (s === 'PENDING' || s === 'submitted') return 'pending'
    if (s === 'STARTED' || s === 'PROGRESS') return 'processing'
    if (s === 'SUCCESS') return 'success'
    if (s === 'FAILURE') return 'error'
    return 'pending'
  }

  function getStatusLabel(s) {
    if (!s) return 'Ready'
    return s
  }

  return (
    <div className="container">
      <div className="card">
        <h1>🎵 Audio Processing Platform</h1>
        <p className="subtitle">Choose a tool and process your audio files with advanced speech analysis</p>

        {!selectedTool ? (
          <div className="tool-grid">
            {TOOLS.map(tool => (
              <div
                key={tool.id}
                className="tool-card"
                onClick={() => setSelectedTool(tool.id)}
              >
                <div className="tool-icon">{tool.name.split(' ')[0]}</div>
                <h3>{tool.name.substring(2)}</h3>
                <p>{tool.desc}</p>
              </div>
            ))}
          </div>
        ) : selectedTool === 'pitch-shifter' ? (
          <PitchShifter onBack={resetForm} />
        ) : (
          <>
            <div className="tool-header">
              <button className="back-button" onClick={resetForm}>
                ← Back to Tools
              </button>
              <h2>{TOOLS.find(t => t.id === selectedTool)?.name}</h2>
            </div>

            <div className="upload-section">
              {selectedTool === 'url2wav' ? (
                <div className="url-input-wrapper">
                  <input
                    type="text"
                    placeholder="Enter audio URL (e.g., https://example.com/audio.mp3)"
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
                    onChange={(e) => setFile(e.target.files[0])}
                  />
                  <label htmlFor="file-input" className={`file-input-label ${file ? 'has-file' : ''}`}>
                    <span className="file-icon">{file ? '✓' : '📁'}</span>
                    <span>{file ? file.name : 'Choose an audio file or drag it here'}</span>
                  </label>
                </div>
              )}
              <button 
                onClick={processAudio} 
                disabled={(selectedTool !== 'url2wav' && !file) || (selectedTool === 'url2wav' && !url) || uploading}
              >
                {uploading ? (
                  <>
                    Processing...
                    <span className="loader"></span>
                  </>
                ) : (
                  'Process Audio'
                )}
              </button>
            </div>

            {task && (
              <div className="status-panel">
                <div className="status-row">
                  <span className="status-label">Task ID:</span>
                  <span className="status-value" style={{fontFamily: 'monospace', fontSize: '13px'}}>
                    {task}
                  </span>
                </div>
                <div className="status-row">
                  <span className="status-label">Status:</span>
                  <span className="status-value">
                    <span className={`status-badge ${getStatusBadgeClass(status)}`}>
                      {getStatusLabel(status)}
                    </span>
                    {status === 'STARTED' || status === 'PROGRESS' ? (
                      <span className="loader"></span>
                    ) : null}
                  </span>
                </div>
                {result && (
                  <div className="status-row">
                    <span className="status-label">Result:</span>
                    <div className="status-value">
                      <pre>{JSON.stringify(result, null, 2)}</pre>
                    </div>
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
