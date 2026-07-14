'use client'

import { useState, useRef } from 'react'

interface Camera {
  id: number
  name: string
  stream_url: string | null
  is_active: boolean
}

interface Props {
  camera: Camera
  onUpdateIp: (cameraId: number, streamUrl: string | null) => void
  onFullscreen: () => void
}

export default function LiveCamCell({ camera, onUpdateIp, onFullscreen }: Props) {
  const parseStreamUrl = (url: string | null) => {
    if (!url) return { ip: '', port: '8080' }
    try {
      const u = new URL(url)
      return { ip: u.hostname, port: u.port || '8080' }
    } catch {
      return { ip: '', port: '8080' }
    }
  }

  const initial = parseStreamUrl(camera.stream_url)
  const [ip, setIp] = useState(initial.ip)
  const [port, setPort] = useState(initial.port)
  const [isHovering, setIsHovering] = useState(false)
  const [streamError, setStreamError] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const imgRef = useRef<HTMLImageElement>(null)

  const isStreaming = !!camera.stream_url && !streamError
  const hasConfig = !!camera.stream_url

  const handleConnect = async () => {
    if (!ip.trim()) return
    setConnecting(true)
    setStreamError(false)
    const url = `http://${ip.trim()}:${port}/video`
    await onUpdateIp(camera.id, url)
    setConnecting(false)
  }

  const handleDisconnect = async () => {
    setStreamError(false)
    await onUpdateIp(camera.id, null)
  }

  const handleRetry = () => {
    setStreamError(false)
    if (camera.stream_url) {
      onUpdateIp(camera.id, camera.stream_url)
    }
  }

  /* ── Shared cell wrapper ── */
  const cellStyle: React.CSSProperties = {
    position: 'relative',
    background: 'var(--bg-card)',
    border: isStreaming
      ? '1px solid rgba(99, 102, 241, 0.35)'
      : '1px solid var(--border-color)',
    borderRadius: 'var(--radius-md)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    backdropFilter: 'blur(16px)',
    transition: 'border-color 0.3s, box-shadow 0.3s',
    boxShadow: isStreaming ? '0 0 20px rgba(99, 102, 241, 0.08)' : '0 4px 20px rgba(0,0,0,0.2)',
  }

  /* ── Input shared styles ── */
  const inputStyle: React.CSSProperties = {
    width: '80%', maxWidth: 240,
    padding: '0.65rem 0.9rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-color)',
    background: 'rgba(0,0,0,0.25)',
    color: 'var(--text-primary)',
    fontSize: '0.9rem',
    fontFamily: 'var(--font-sans)',
    outline: 'none',
    transition: 'var(--transition)',
  }

  const portInputStyle: React.CSSProperties = {
    width: 72,
    padding: '0.55rem 0.6rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-color)',
    background: 'rgba(0,0,0,0.25)',
    color: 'var(--text-primary)',
    fontSize: '0.85rem',
    fontFamily: 'var(--font-sans)',
    textAlign: 'center',
    outline: 'none',
    transition: 'var(--transition)',
  }

  /* ════════════════════════════════════════════
     STATE A — Chưa có IP
     ════════════════════════════════════════════ */
  if (!hasConfig) {
    return (
      <div style={cellStyle}>
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 14, padding: '1.5rem',
        }}>
          {/* Camera icon */}
          <div style={{
            width: 56, height: 56, borderRadius: '50%',
            background: 'rgba(99, 102, 241, 0.1)',
            border: '1px solid rgba(99, 102, 241, 0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.3rem', color: 'var(--primary)', marginBottom: 4,
          }}>
            <i className="fa-solid fa-video-slash" />
          </div>

          <div style={{ fontFamily: 'var(--font-display)', fontSize: '0.95rem', color: 'var(--text-primary)', fontWeight: 600 }}>
            {camera.name}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: -6 }}>
            Nhập IP để bắt đầu stream
          </div>

          <input
            type="text"
            placeholder="IP (VD: 192.168.1.100)"
            value={ip}
            onChange={e => setIp(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleConnect()}
            style={inputStyle}
            onFocus={e => {
              e.currentTarget.style.borderColor = 'var(--primary)'
              e.currentTarget.style.boxShadow = '0 0 0 3px var(--primary-glow)'
            }}
            onBlur={e => {
              e.currentTarget.style.borderColor = 'var(--border-color)'
              e.currentTarget.style.boxShadow = 'none'
            }}
          />

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="text"
              value={port}
              onChange={e => setPort(e.target.value)}
              style={portInputStyle}
              onFocus={e => {
                e.currentTarget.style.borderColor = 'var(--primary)'
                e.currentTarget.style.boxShadow = '0 0 0 3px var(--primary-glow)'
              }}
              onBlur={e => {
                e.currentTarget.style.borderColor = 'var(--border-color)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            />
            <button
              onClick={handleConnect}
              disabled={!ip.trim() || connecting}
              className="btn"
              style={{
                padding: '0.6rem 1.4rem',
                background: ip.trim() ? 'var(--primary)' : 'rgba(255,255,255,0.05)',
                color: ip.trim() ? '#fff' : 'var(--text-muted)',
                border: ip.trim() ? 'none' : '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.88rem',
                fontWeight: 600,
                cursor: ip.trim() ? 'pointer' : 'not-allowed',
                transition: 'var(--transition)',
              }}
            >
              {connecting ? (
                <><i className="fa-solid fa-spinner fa-spin" /> Đang kết nối...</>
              ) : (
                <><i className="fa-solid fa-plug" /> Kết nối</>
              )}
            </button>
          </div>
        </div>
      </div>
    )
  }

  /* ════════════════════════════════════════════
     STATE C — Lỗi kết nối
     ════════════════════════════════════════════ */
  if (streamError) {
    return (
      <div style={cellStyle}>
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 12, padding: '1.5rem',
        }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.3rem', color: 'var(--danger)', marginBottom: 4,
          }}>
            <i className="fa-solid fa-triangle-exclamation" />
          </div>

          <div style={{ fontFamily: 'var(--font-display)', fontSize: '0.95rem', color: 'var(--text-primary)', fontWeight: 600 }}>
            {camera.name}
          </div>
          <div style={{ color: 'var(--danger)', fontSize: '0.85rem', fontWeight: 500 }}>
            Không kết nối được
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', wordBreak: 'break-all', textAlign: 'center' }}>
            {camera.stream_url}
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleRetry} className="btn btn-sm" style={{
              background: 'var(--primary)', color: '#fff', padding: '0.5rem 1rem',
            }}>
              <i className="fa-solid fa-rotate-right" /> Thử lại
            </button>
            <button onClick={handleDisconnect} className="btn btn-sm btn-danger" style={{
              padding: '0.5rem 1rem',
            }}>
              <i className="fa-solid fa-trash" /> Xóa
            </button>
          </div>
        </div>
      </div>
    )
  }

  /* ════════════════════════════════════════════
     STATE B — Đang stream
     ════════════════════════════════════════════ */
  const streamUrl = camera.stream_url + (camera.stream_url?.includes('?') ? '&' : '?') + 't=' + Date.now()

  return (
    <div
      style={cellStyle}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {/* Video area */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', borderRadius: 'var(--radius-md) var(--radius-md) 0 0' }}>
        <img
          ref={imgRef}
          src={streamUrl}
          alt={camera.name}
          onLoad={() => setStreamError(false)}
          onError={() => setStreamError(true)}
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />

        {/* Hover overlay — fullscreen button */}
        {isHovering && (
          <div
            onClick={onFullscreen}
            style={{
              position: 'absolute', inset: 0,
              background: 'rgba(0, 0, 0, 0.55)',
              backdropFilter: 'blur(2px)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer',
              animation: 'livecamFadeIn 0.2s ease',
            }}
          >
            <div style={{
              width: 64, height: 64, borderRadius: '50%',
              background: 'rgba(255,255,255,0.92)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
              transition: 'transform 0.2s',
            }}>
              <i className="fa-solid fa-expand" style={{ color: 'var(--bg-primary)', fontSize: '1.4rem' }} />
            </div>
          </div>
        )}
      </div>

      {/* Footer bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0.45rem 0.85rem',
        background: 'rgba(0, 0, 0, 0.35)',
        borderTop: '1px solid var(--border-color)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
          <span className="status-dot online" style={{ width: 7, height: 7, flexShrink: 0 }} />
          <span style={{
            fontFamily: 'var(--font-display)',
            fontSize: '0.82rem', fontWeight: 600,
            color: 'var(--text-primary)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {camera.name}
          </span>
          <span style={{
            fontSize: '0.78rem', color: 'var(--text-muted)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            — {ip || camera.stream_url}
          </span>
        </div>

        <button
          onClick={handleDisconnect}
          className="btn btn-sm btn-danger"
          style={{
            padding: '0.25rem 0.5rem', fontSize: '0.75rem',
            flexShrink: 0, marginLeft: 8,
          }}
          title="Tắt camera"
        >
          <i className="fa-solid fa-xmark" />
        </button>
      </div>

      {/* CSS for animation */}
      <style jsx>{`
        @keyframes livecamFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </div>
  )
}
