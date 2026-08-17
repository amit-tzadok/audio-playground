import React from 'react'

// CSS-only frosted glass button (backdrop-filter blur + translucent surface
// + glossy highlight). A real liquid-glass-react version was tried first,
// but that library self-centers each instance via a top:50%/left:50% +
// translate(-50%,-50%) trick that only cancels out when the element is the
// sole child of a shrink-wrapped container — inside our real flex rows with
// sibling buttons/text it threw instances hundreds of pixels off. This gets
// the same visual language reliably.
export default function GlassButton({
  children,
  onClick,
  disabled = false,
  active = false,
  variant = 'pill',
  className = '',
  type = 'button',
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`glass-btn glass-btn--${variant} ${active ? 'is-active' : ''} ${className}`}
    >
      <span className="glass-btn-label">{children}</span>
    </button>
  )
}
