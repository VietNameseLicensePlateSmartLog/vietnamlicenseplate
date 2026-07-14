'use client'

import LiveCamCell from './LiveCamCell'

interface Camera {
  id: number
  name: string
  stream_url: string | null
  is_active: boolean
}

interface Props {
  cameras: Camera[]
  onUpdateIp: (cameraId: number, streamUrl: string | null) => void
  onFullscreen: (cameraId: number) => void
}

export default function LiveCamGrid({ cameras, onUpdateIp, onFullscreen }: Props) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gridTemplateRows: '1fr 1fr',
      gap: '0.75rem',
      height: 'calc(100vh - 140px)',
    }}>
      {cameras.slice(0, 4).map(cam => (
        <LiveCamCell
          key={cam.id}
          camera={cam}
          onUpdateIp={onUpdateIp}
          onFullscreen={() => onFullscreen(cam.id)}
        />
      ))}
    </div>
  )
}
