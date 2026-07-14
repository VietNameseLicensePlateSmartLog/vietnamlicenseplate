'use client';

import { useState, useEffect, useCallback } from 'react';
import { API_BASE } from '@/lib/api';

interface Camera {
  id: number;
  name: string;
  rtsp_url: string;
  region_id: number | null;
  is_active: boolean;
  is_online: boolean;
  fps_target: number;
  description: string | null;
  region_name: string | null;
  created_at: string | null;
}

interface Region {
  id: number;
  name: string;
}

export default function AdminCamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
  const [form, setForm] = useState({
    name: '',
    rtsp_url: '',
    region_id: null as number | null,
    fps_target: 10,
    description: '',
  });

  const fetchData = useCallback(async () => {
    try {
      const [camRes, regRes] = await Promise.all([
        fetch(`${API_BASE}/cameras`),
        fetch(`${API_BASE}/regions`),
      ]);
      if (camRes.ok) setCameras(await camRes.json());
      if (regRes.ok) setRegions(await regRes.json());
    } catch (e) {
      console.error('Fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const openCreate = () => {
    setEditingCamera(null);
    setForm({ name: '', rtsp_url: '', region_id: null, fps_target: 10, description: '' });
    setShowModal(true);
  };

  const openEdit = (cam: Camera) => {
    setEditingCamera(cam);
    setForm({
      name: cam.name,
      rtsp_url: cam.rtsp_url,
      region_id: cam.region_id,
      fps_target: cam.fps_target,
      description: cam.description || '',
    });
    setShowModal(true);
  };

  const handleSubmit = async () => {
    if (!form.name || !form.rtsp_url) {
      alert('Vui lòng nhập tên camera và RTSP URL.');
      return;
    }
    try {
      const url = editingCamera
        ? `${API_BASE}/cameras/${editingCamera.id}`
        : `${API_BASE}/cameras`;
      const method = editingCamera ? 'PUT' : 'POST';
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (res.ok) {
        setShowModal(false);
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || 'Lỗi khi lưu camera.');
      }
    } catch (e) {
      alert('Không thể kết nối đến server.');
    }
  };

  const handleDelete = async (cam: Camera) => {
    if (!confirm(`Xác nhận xóa camera "${cam.name}"?`)) return;
    try {
      await fetch(`${API_BASE}/cameras/${cam.id}`, { method: 'DELETE' });
      fetchData();
    } catch (e) {
      alert('Lỗi khi xóa camera.');
    }
  };

  const handleToggle = async (cam: Camera) => {
    try {
      await fetch(`${API_BASE}/cameras/${cam.id}/toggle`, { method: 'POST' });
      fetchData();
    } catch (e) {
      alert('Lỗi khi bật/tắt camera.');
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center' }}>
        <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: '#818cf8' }}></i>
        <p style={{ color: '#94a3b8', marginTop: '1rem' }}>Đang tải...</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#e2e8f0', margin: 0 }}>
            📹 Quản lý Camera
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '4px' }}>
            Quản lý {cameras.length} camera IP (RTSP)
          </p>
        </div>
        <button onClick={openCreate} style={{
          padding: '10px 20px', borderRadius: '8px', border: 'none',
          background: '#3b82f6', color: 'white', fontWeight: 600, cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: '8px',
        }}>
          <i className="fa-solid fa-plus"></i> Thêm Camera Mới
        </button>
      </div>

      {/* Table */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.7)',
        borderRadius: '12px',
        border: '1px solid rgba(51, 65, 85, 0.4)',
        overflow: 'hidden',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(51, 65, 85, 0.5)' }}>
              {['ID', 'Tên', 'RTSP URL', 'Vùng', 'FPS', 'Trạng thái', 'Thao tác'].map(h => (
                <th key={h} style={{
                  padding: '12px 16px', textAlign: 'left', color: '#94a3b8',
                  fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600,
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cameras.map(cam => (
              <tr key={cam.id} style={{ borderBottom: '1px solid rgba(51, 65, 85, 0.3)' }}>
                <td style={{ padding: '12px 16px', color: '#64748b', fontSize: '0.85rem' }}>{cam.id}</td>
                <td style={{ padding: '12px 16px', color: '#e2e8f0', fontWeight: 600 }}>{cam.name}</td>
                <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: '0.8rem', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {cam.rtsp_url}
                </td>
                <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: '0.85rem' }}>
                  {cam.region_name || '--'}
                </td>
                <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: '0.85rem' }}>
                  {cam.fps_target}
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                    padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 600,
                    background: cam.is_active
                      ? (cam.is_online ? 'rgba(34,197,94,0.15)' : 'rgba(234,179,8,0.15)')
                      : 'rgba(107,114,128,0.15)',
                    color: cam.is_active
                      ? (cam.is_online ? '#4ade80' : '#fbbf24')
                      : '#9ca3af',
                  }}>
                    <span style={{
                      width: '6px', height: '6px', borderRadius: '50%',
                      background: cam.is_active ? (cam.is_online ? '#22c55e' : '#eab308') : '#6b7280',
                    }} />
                    {cam.is_active ? (cam.is_online ? 'Online' : 'Starting') : 'OFF'}
                  </span>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button onClick={() => openEdit(cam)} style={{
                      padding: '4px 10px', borderRadius: '4px', border: 'none',
                      background: 'rgba(59,130,246,0.2)', color: '#60a5fa', cursor: 'pointer', fontSize: '0.75rem',
                    }}>Sửa</button>
                    <button onClick={() => handleToggle(cam)} style={{
                      padding: '4px 10px', borderRadius: '4px', border: 'none',
                      background: cam.is_active ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)',
                      color: cam.is_active ? '#f87171' : '#4ade80', cursor: 'pointer', fontSize: '0.75rem',
                    }}>
                      {cam.is_active ? 'Tắt' : 'Bật'}
                    </button>
                    <button onClick={() => handleDelete(cam)} style={{
                      padding: '4px 10px', borderRadius: '4px', border: 'none',
                      background: 'rgba(239,68,68,0.1)', color: '#ef4444', cursor: 'pointer', fontSize: '0.75rem',
                    }}>Xóa</button>
                  </div>
                </td>
              </tr>
            ))}
            {cameras.length === 0 && (
              <tr>
                <td colSpan={7} style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
                  Chưa có camera nào.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {showModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }} onClick={() => setShowModal(false)}>
          <div style={{
            background: '#1e293b', borderRadius: '12px', padding: '24px',
            width: '480px', maxWidth: '90vw', border: '1px solid rgba(51,65,85,0.5)',
          }} onClick={e => e.stopPropagation()}>
            <h3 style={{ color: '#e2e8f0', margin: '0 0 16px 0', fontSize: '1.1rem' }}>
              {editingCamera ? 'Sửa Camera' : 'Thêm Camera Mới'}
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>Tên camera *</label>
                <input
                  value={form.name}
                  onChange={e => setForm({...form, name: e.target.value})}
                  placeholder="VD: Cam Cổng Chính"
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: '6px',
                    border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                    color: '#e2e8f0', fontSize: '0.9rem',
                  }}
                />
              </div>
              <div>
                <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>RTSP URL *</label>
                <input
                  value={form.rtsp_url}
                  onChange={e => setForm({...form, rtsp_url: e.target.value})}
                  placeholder="rtsp://admin:pass@192.168.1.x/stream"
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: '6px',
                    border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                    color: '#e2e8f0', fontSize: '0.9rem',
                  }}
                />
              </div>
              <div style={{ display: 'flex', gap: '12px' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>Vùng camera</label>
                  <select
                    value={form.region_id ?? ''}
                    onChange={e => setForm({...form, region_id: e.target.value ? Number(e.target.value) : null})}
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: '6px',
                      border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                      color: '#e2e8f0', fontSize: '0.9rem',
                    }}
                  >
                    <option value="">-- Chọn vùng --</option>
                    {regions.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                  </select>
                </div>
                <div style={{ width: '100px' }}>
                  <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>FPS</label>
                  <input
                    type="number"
                    min={1} max={30}
                    value={form.fps_target}
                    onChange={e => setForm({...form, fps_target: Number(e.target.value)})}
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: '6px',
                      border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                      color: '#e2e8f0', fontSize: '0.9rem',
                    }}
                  />
                </div>
              </div>
              <div>
                <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>Mô tả</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm({...form, description: e.target.value})}
                  rows={2}
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: '6px',
                    border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                    color: '#e2e8f0', fontSize: '0.9rem', resize: 'vertical',
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
              <button onClick={() => setShowModal(false)} style={{
                padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(51,65,85,0.5)',
                background: 'transparent', color: '#94a3b8', cursor: 'pointer',
              }}>Hủy</button>
              <button onClick={handleSubmit} style={{
                padding: '8px 20px', borderRadius: '6px', border: 'none',
                background: '#3b82f6', color: 'white', fontWeight: 600, cursor: 'pointer',
              }}>
                {editingCamera ? 'Cập nhật' : 'Tạo mới'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
