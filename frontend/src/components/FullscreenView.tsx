'use client'

import { useEffect } from 'react'

interface Camera {
  id: number
  name: string
  stream_url: string | null
}

interface Props {
  camera: Camera
  onClose: () => void
}

export default function FullscreenView({ camera, onClose }: Props) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  if (!camera.stream_url) return null

  const streamUrl = camera.stream_url + (camera.stream_url.includes('?') ? '&' : '?') + 't=' + Date.now()

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0, 0, 0, 0.95)',
        backdropFilter: 'blur(8px)',
        display: 'flex', flexDirection: 'column',
        animation: 'livecamFsIn 0.25s ease',
      }}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        style={{
          position: 'absolute', top: 20, left: 20, zIndex: 1001,
          width: 44, height: 44, borderRadius: '50%',
          background: 'rgba(255,255,255,0.1)',
          border: '1px solid rgba(255,255,255,0.15)',
          color: '#fff', fontSize: 18, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'var(--transition)',
        }}
        onMouseEnter={e => {
          e.currentTarget.style.background = 'var(--danger)'
          e.currentTarget.style.borderColor = 'var(--danger)'
        }}
        onMouseLeave={e => {
          e.currentTarget.style.background = 'rgba(255,255,255,0.1)'
          e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'
        }}
      >
        <i className="fa-solid fa-xmark" />
      </button>

      {/* Stream */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '60px 24px 80px' }}>
        <img
          src={streamUrl}
          alt={camera.name}
          onClick={e => e.stopPropagation()}
          style={{
            maxWidth: '100%', maxHeight: '100%',
            objectFit: 'contain',
            borderRadius: 'var(--radius-md)',
            boxShadow: '0 10px 40px rgba(0, 0, 0, 0.5)',
          }}
        />
      </div>

      {/* Footer */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        padding: '14px 24px',
        background: 'linear-gradient(transparent, rgba(0,0,0,0.85))',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12,
        fontSize: '0.88rem',
      }}>
        <span className="status-dot online" style={{ width: 8, height: 8 }} />
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--text-primary)' }}>
          {camera.name}
        </span>
        <span style={{ color: 'var(--text-muted)' }}>—</span>
        <span style={{ color: 'var(--text-secondary)' }}>{camera.stream_url}</span>
      </div>

      <style jsx>{`
        @keyframes livecamFsIn {
          from { opacity: 0; transform: scale(0.97); }
          to { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  )
}
