import React from 'react'

// percent: 0-100 for a determinate ring, or omit/null for an indeterminate
// spinner (a fixed arc that continuously rotates).
export default function CircularProgress({ percent = null, size = 56, strokeWidth = 6, showLabel = true }) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const indeterminate = percent === null || percent === undefined
  const clamped = indeterminate ? 0 : Math.max(0, Math.min(100, percent))

  const dashOffset = indeterminate
    ? circumference * 0.25
    : circumference - (clamped / 100) * circumference

  return (
    <div className="circular-progress-wrap" style={{ width: size, height: size }}>
      <svg
        className={`circular-progress ${indeterminate ? 'indeterminate' : ''}`}
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
      >
        <circle
          className="circular-progress-track"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
        />
        <circle
          className="circular-progress-fill"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      {showLabel && !indeterminate && size >= 40 && (
        <span className="circular-progress-label">{Math.round(clamped)}%</span>
      )}
    </div>
  )
}
