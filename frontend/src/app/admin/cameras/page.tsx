'use client';

import { useState, useEffect, useCallback } from 'react';
import { API_BASE } from '@/lib/api';

interface Camera {
  id: number;
  name: string;
  rtsp_url: string;
  stream_url: string | null;
  region_id: number | null;
  is_active: boolean;
  is_online: boolean;
  fps_target: number;
  description: string | null;
  region_name: string | null;
  created_at: string | null;
  // IP Camera connection fields
  stream_type: string;
  username: string | null;
  connect_timeout: number;
  reconnect_interval: number;
  max_reconnect_attempts: number;
  last_connected_at: string | null;
  last_error: string | null;
}

interface Region {
  id: number;
  name: string;
}

interface TestResult {
  success: boolean;
  message: string;
  fps: number | null;
  resolution: string | null;
}

const defaultForm = {
  name: '',
  rtsp_url: '',
  stream_type: 'rtsp',
  username: '',
  password: '',
  region_id: null as number | null,
  fps_target: 10,
  connect_timeout: 10,
  reconnect_interval: 5,
  max_reconnect_attempts: 10,
  description: '',
};

export default function AdminCamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
  const [form, setForm] = useState(defaultForm);
  const [showPassword, setShowPassword] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);

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
    setForm(defaultForm);
    setTestResult(null);
    setShowPassword(false);
    setShowModal(true);
  };

  const openEdit = (cam: Camera) => {
    setEditingCamera(cam);
    setForm({
      name: cam.name,
      rtsp_url: cam.rtsp_url,
      stream_type: cam.stream_type || 'rtsp',
      username: cam.username || '',
      password: '',  // Không hiển thị password cũ
      region_id: cam.region_id,
      fps_target: cam.fps_target,
      connect_timeout: cam.connect_timeout || 10,
      reconnect_interval: cam.reconnect_interval || 5,
      max_reconnect_attempts: cam.max_reconnect_attempts || 10,
      description: cam.description || '',
    });
    setTestResult(null);
    setShowPassword(false);
    setShowModal(true);
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const body: Record<string, unknown> = {
        rtsp_url: form.rtsp_url,
        stream_type: form.stream_type,
        connect_timeout: form.connect_timeout,
      };
      if (form.username) body.username = form.username;
      if (form.password) body.password = form.password;

      const url = editingCamera
        ? `${API_BASE}/cameras/${editingCamera.id}/test`
        : `${API_BASE}/cameras/test-url`;

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data: TestResult = await res.json();
      setTestResult(data);
    } catch {
      setTestResult({ success: false, message: 'Không thể kết nối server.', fps: null, resolution: null });
    } finally {
      setTesting(false);
    }
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

      // Build body — chỉ gửi password nếu có nhập mới
      const body: Record<string, unknown> = {
        name: form.name,
        rtsp_url: form.rtsp_url,
        stream_type: form.stream_type,
        region_id: form.region_id,
        fps_target: form.fps_target,
        connect_timeout: form.connect_timeout,
        reconnect_interval: form.reconnect_interval,
        max_reconnect_attempts: form.max_reconnect_attempts,
        description: form.description || null,
      };
      if (form.username) body.username = form.username;
      if (form.password) body.password = form.password;

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setShowModal(false);
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || 'Lỗi khi lưu camera.');
      }
    } catch {
      alert('Không thể kết nối đến server.');
    }
  };

  const handleDelete = async (cam: Camera) => {
    if (!confirm(`Xác nhận xóa camera "${cam.name}"?`)) return;
    try {
      await fetch(`${API_BASE}/cameras/${cam.id}`, { method: 'DELETE' });
      fetchData();
    } catch {
      alert('Lỗi khi xóa camera.');
    }
  };

  const handleToggle = async (cam: Camera) => {
    try {
      await fetch(`${API_BASE}/cameras/${cam.id}/toggle`, { method: 'POST' });
      fetchData();
    } catch {
      alert('Lỗi khi bật/tắt camera.');
    }
  };

  const getStreamTypeIcon = (type: string) => {
    switch (type) {
      case 'rtsp': return '🎬';
      case 'http': return '🌐';
      case 'rtmp': return '📡';
      default: return '📹';
    }
  };

  const getStatusInfo = (cam: Camera) => {
    if (!cam.is_active) return { label: 'OFF', bg: 'rgba(107,114,128,0.15)', color: '#9ca3af', dot: '#6b7280' };
    if (cam.is_online) return { label: 'Online', bg: 'rgba(34,197,94,0.15)', color: '#4ade80', dot: '#22c55e' };
    if (cam.last_error) return { label: 'Error', bg: 'rgba(239,68,68,0.15)', color: '#f87171', dot: '#ef4444' };
    return { label: 'Starting', bg: 'rgba(234,179,8,0.15)', color: '#fbbf24', dot: '#eab308' };
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
            📹 Quản lý Camera IP
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '4px' }}>
            Quản lý {cameras.length} camera — RTSP / HTTP / RTMP
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
              {['ID', 'Tên', 'Loại', 'RTSP URL', 'Vùng', 'FPS', 'Trạng thái', 'Thao tác'].map(h => (
                <th key={h} style={{
                  padding: '12px 16px', textAlign: 'left', color: '#94a3b8',
                  fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600,
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cameras.map(cam => {
              const status = getStatusInfo(cam);
              return (
                <tr key={cam.id} style={{ borderBottom: '1px solid rgba(51, 65, 85, 0.3)' }}>
                  <td style={{ padding: '12px 16px', color: '#64748b', fontSize: '0.85rem' }}>{cam.id}</td>
                  <td style={{ padding: '12px 16px', color: '#e2e8f0', fontWeight: 600 }}>{cam.name}</td>
                  <td style={{ padding: '12px 16px', fontSize: '0.85rem' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      {getStreamTypeIcon(cam.stream_type)} {cam.stream_type?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: '0.8rem', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={cam.rtsp_url}>
                    {cam.rtsp_url}
                  </td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: '0.85rem' }}>
                    {cam.region_name || '--'}
                  </td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: '0.85rem' }}>
                    {cam.fps_target}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <span title={cam.last_error || undefined} style={{
                      display: 'inline-flex', alignItems: 'center', gap: '6px',
                      padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 600,
                      background: status.bg, color: status.color, cursor: cam.last_error ? 'help' : 'default',
                    }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: status.dot }} />
                      {status.label}
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
              );
            })}
            {cameras.length === 0 && (
              <tr>
                <td colSpan={8} style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
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
            width: '560px', maxWidth: '90vw', maxHeight: '90vh', overflow: 'auto',
            border: '1px solid rgba(51,65,85,0.5)',
          }} onClick={e => e.stopPropagation()}>
            <h3 style={{ color: '#e2e8f0', margin: '0 0 16px 0', fontSize: '1.1rem' }}>
              {editingCamera ? '✏️ Sửa Camera' : '📹 Thêm Camera Mới'}
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* Tên camera */}
              <div>
                <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>Tên camera *</label>
                <input
                  value={form.name}
                  onChange={e => setForm({...form, name: e.target.value})}
                  placeholder="VD: Cam Cổng Chính"
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: '6px',
                    border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                    color: '#e2e8f0', fontSize: '0.9rem', boxSizing: 'border-box',
                  }}
                />
              </div>

              {/* Stream type + FPS */}
              <div style={{ display: 'flex', gap: '12px' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>Loại stream</label>
                  <select
                    value={form.stream_type}
                    onChange={e => setForm({...form, stream_type: e.target.value})}
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: '6px',
                      border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                      color: '#e2e8f0', fontSize: '0.9rem',
                    }}
                  >
                    <option value="rtsp">🎬 RTSP</option>
                    <option value="http">🌐 HTTP/MJPEG</option>
                    <option value="rtmp">📡 RTMP</option>
                  </select>
                </div>
                <div style={{ width: '100px' }}>
                  <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>FPS</label>
                  <input
                    type="number" min={1} max={30}
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

              {/* RTSP URL */}
              <div>
                <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>RTSP URL *</label>
                <input
                  value={form.rtsp_url}
                  onChange={e => setForm({...form, rtsp_url: e.target.value})}
                  placeholder="rtsp://192.168.1.x:554/stream"
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: '6px',
                    border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                    color: '#e2e8f0', fontSize: '0.9rem', boxSizing: 'border-box',
                  }}
                />
              </div>

              {/* Username + Password */}
              <div style={{ display: 'flex', gap: '12px' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>Username (nếu có auth)</label>
                  <input
                    value={form.username}
                    onChange={e => setForm({...form, username: e.target.value})}
                    placeholder="admin"
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: '6px',
                      border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                      color: '#e2e8f0', fontSize: '0.9rem', boxSizing: 'border-box',
                    }}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>Password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={form.password}
                      onChange={e => setForm({...form, password: e.target.value})}
                      placeholder={editingCamera ? "(để trống nếu không đổi)" : "••••••"}
                      style={{
                        width: '100%', padding: '8px 32px 8px 12px', borderRadius: '6px',
                        border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                        color: '#e2e8f0', fontSize: '0.9rem', boxSizing: 'border-box',
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      style={{
                        position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)',
                        background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px',
                      }}
                    >
                      {showPassword ? '🙈' : '👁️'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Vùng */}
              <div>
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

              {/* Connection settings */}
              <div style={{
                padding: '12px', borderRadius: '8px',
                background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)',
              }}>
                <div style={{ color: '#60a5fa', fontSize: '0.8rem', fontWeight: 600, marginBottom: '8px' }}>
                  ⚙️ Cài đặt kết nối Internet
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <div style={{ flex: 1 }}>
                    <label style={{ color: '#94a3b8', fontSize: '0.75rem', display: 'block', marginBottom: '4px' }}>Timeout (giây)</label>
                    <input
                      type="number" min={3} max={60}
                      value={form.connect_timeout}
                      onChange={e => setForm({...form, connect_timeout: Number(e.target.value)})}
                      style={{
                        width: '100%', padding: '6px 8px', borderRadius: '4px',
                        border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                        color: '#e2e8f0', fontSize: '0.85rem',
                      }}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={{ color: '#94a3b8', fontSize: '0.75rem', display: 'block', marginBottom: '4px' }}>Reconnect (giây)</label>
                    <input
                      type="number" min={1} max={60}
                      value={form.reconnect_interval}
                      onChange={e => setForm({...form, reconnect_interval: Number(e.target.value)})}
                      style={{
                        width: '100%', padding: '6px 8px', borderRadius: '4px',
                        border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                        color: '#e2e8f0', fontSize: '0.85rem',
                      }}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={{ color: '#94a3b8', fontSize: '0.75rem', display: 'block', marginBottom: '4px' }}>Max retries</label>
                    <input
                      type="number" min={0} max={100}
                      value={form.max_reconnect_attempts}
                      onChange={e => setForm({...form, max_reconnect_attempts: Number(e.target.value)})}
                      style={{
                        width: '100%', padding: '6px 8px', borderRadius: '4px',
                        border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                        color: '#e2e8f0', fontSize: '0.85rem',
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Mô tả */}
              <div>
                <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>Mô tả</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm({...form, description: e.target.value})}
                  rows={2}
                  placeholder="VD: Camera giám sát cổng chính công ty"
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: '6px',
                    border: '1px solid rgba(51,65,85,0.5)', background: '#0f172a',
                    color: '#e2e8f0', fontSize: '0.9rem', resize: 'vertical', boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>

            {/* Test connection result */}
            {testResult && (
              <div style={{
                marginTop: '12px', padding: '12px', borderRadius: '8px',
                background: testResult.success ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                border: `1px solid ${testResult.success ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ fontSize: '1rem' }}>{testResult.success ? '✅' : '❌'}</span>
                  <span style={{ color: testResult.success ? '#4ade80' : '#f87171', fontWeight: 600, fontSize: '0.85rem' }}>
                    {testResult.success ? 'Kết nối thành công!' : 'Kết nối thất bại'}
                  </span>
                </div>
                <p style={{ color: '#94a3b8', fontSize: '0.8rem', margin: 0 }}>{testResult.message}</p>
                {testResult.success && testResult.fps && (
                  <p style={{ color: '#64748b', fontSize: '0.75rem', margin: '4px 0 0 0' }}>
                    Resolution: {testResult.resolution} | FPS: ~{testResult.fps}
                  </p>
                )}
              </div>
            )}

            {/* Action buttons */}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '20px' }}>
              <button
                onClick={handleTest}
                disabled={testing || !form.rtsp_url}
                style={{
                  padding: '8px 16px', borderRadius: '6px',
                  border: '1px solid rgba(234,179,8,0.4)',
                  background: 'rgba(234,179,8,0.1)', color: '#fbbf24',
                  cursor: testing || !form.rtsp_url ? 'not-allowed' : 'pointer',
                  opacity: testing || !form.rtsp_url ? 0.5 : 1,
                  fontWeight: 600, fontSize: '0.85rem',
                  display: 'flex', alignItems: 'center', gap: '6px',
                }}
              >
                {testing ? <i className="fa-solid fa-spinner fa-spin"></i> : '🧪'}
                Test kết nối
              </button>
              <div style={{ display: 'flex', gap: '10px' }}>
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
        </div>
      )}
    </div>
  );
}
