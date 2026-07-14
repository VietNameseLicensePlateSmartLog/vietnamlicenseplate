'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { API_BASE } from '@/lib/api'
import AnimatedBackground from '@/components/AnimatedBackground'
import LiveCamGrid from '@/components/LiveCamGrid'
import FullscreenView from '@/components/FullscreenView'

interface Camera {
  id: number
  name: string
  stream_url: string | null
  is_active: boolean
}

export default function LiveCamPage() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [fullscreenId, setFullscreenId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_BASE}/cameras`)
      .then(r => r.json())
      .then(data => {
        setCameras(data.cameras || data || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const handleUpdateIp = useCallback(async (cameraId: number, streamUrl: string | null) => {
    await fetch(`${API_BASE}/cameras/${cameraId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stream_url: streamUrl }),
    })
    setCameras(prev => prev.map(c => c.id === cameraId ? { ...c, stream_url: streamUrl } : c))
  }, [])

  const fullscreenCamera = cameras.find(c => c.id === fullscreenId)

  return (
    <div className="app-container" style={{ minHeight: '100vh' }}>
      <AnimatedBackground />

      {/* Header — đồng bộ với navbar */}
      <header className="navbar" style={{ padding: '0.8rem 2.5rem' }}>
        <Link
          href="/home"
          className="btn btn-sm"
          style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-primary)',
            borderRadius: 'var(--radius-md)',
            textDecoration: 'none',
          }}
        >
          <i className="fa-solid fa-arrow-left" /> Home
        </Link>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
          <div style={{
            background: 'linear-gradient(135deg, var(--primary), #8b5cf6)',
            width: 36, height: 36, borderRadius: 'var(--radius-sm)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: '1rem',
          }}>
            <i className="fa-solid fa-video" />
          </div>
          <div>
            <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', fontWeight: 700, lineHeight: 1.2, color: '#fff' }}>
              Live Camera
            </h1>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
              MJPEG Stream • IP Webcam
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div className="api-status" style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
            <span className="status-dot online" />
            <span>{cameras.filter(c => c.stream_url).length} / {cameras.length} camera</span>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="main-content" style={{ padding: '1.5rem 2rem', maxWidth: '100%' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 'calc(100vh - 120px)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: 'var(--primary)' }} />
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Đang tải cameras...</span>
            </div>
          </div>
        ) : (
          <LiveCamGrid
            cameras={cameras}
            onUpdateIp={handleUpdateIp}
            onFullscreen={setFullscreenId}
          />
        )}
      </main>

      {fullscreenCamera && (
        <FullscreenView
          camera={fullscreenCamera}
          onClose={() => setFullscreenId(null)}
        />
      )}
    </div>
  )
}
