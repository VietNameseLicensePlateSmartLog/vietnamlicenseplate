'use client';

import { useState, useEffect } from 'react';
import { API_BASE } from '@/lib/api';

interface RegionStat {
  name: string;
  total_detections: number;
  avg_confidence: number;
}

// Bảng màu cho các cột bar
const BAR_COLORS = [
  '#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
  '#ec4899', '#6366f1', '#14b8a6', '#f97316', '#84cc16', '#a855f7'
];

export default function VariableStats() {
  const [stats, setStats] = useState<RegionStat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchRegionStats = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE}/admin/regions-stats`);
      if (!res.ok) {
        throw new Error('Không thể tải số liệu thống kê khu vực.');
      }
      const data = await res.json();
      setStats(data);
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối API.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRegionStats();
  }, []);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flex: 1, justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  const totalCount = stats.reduce((acc, curr) => acc + curr.total_detections, 0);
  const maxCount = stats.length > 0 ? Math.max(...stats.map(s => s.total_detections), 1) : 1;

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 600 }}>Thống kê theo phân vùng / Camera</h1>
          <p style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.9rem' }}>Phân tích số lượt nhận diện phương tiện theo từng khu vực lắp đặt camera</p>
        </div>
        <button onClick={fetchRegionStats} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <i className="fa-solid fa-rotate"></i> Tải lại
        </button>
      </div>

      {error && (
        <div className="card" style={{ padding: '20px', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#fca5a5', marginBottom: '20px' }}>
          <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '8px' }}></i> {error}
        </div>
      )}

      {/* Biểu đồ cột đứng */}
      <div className="card" style={{ padding: '24px', marginBottom: '20px' }}>
        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Biểu đồ thống kê</h3>
          <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.85rem' }}>
            Tổng số lượt ghi nhận: <strong>{totalCount}</strong> phương tiện
          </p>
        </div>

        {stats.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'rgba(255,255,255,0.3)' }}>Không có dữ liệu</div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '12px', height: '280px', padding: '0 8px' }}>
            {stats.map((item, idx) => {
              const barHeight = maxCount > 0 ? (item.total_detections / maxCount) * 100 : 0;
              const percentage = totalCount > 0 ? (item.total_detections / totalCount) * 100 : 0;
              const color = BAR_COLORS[idx % BAR_COLORS.length];
              return (
                <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%', minWidth: 0 }}>
                  {/* Số liệu trên cột */}
                  <div style={{ marginBottom: '6px', textAlign: 'center' }}>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color }}>{item.total_detections}</div>
                    <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.45)' }}>{percentage.toFixed(1)}%</div>
                  </div>
                  {/* Thanh bar */}
                  <div
                    style={{
                      width: '100%',
                      maxWidth: '80px',
                      height: `${Math.max(barHeight, 2)}%`,
                      background: `linear-gradient(180deg, ${color}, ${color}88)`,
                      borderRadius: '6px 6px 2px 2px',
                      transition: 'height 0.8s ease-out',
                      minHeight: '4px',
                    }}
                  />
                  {/* Tên region */}
                  <div
                    style={{
                      marginTop: '10px',
                      fontSize: '0.78rem',
                      color: 'rgba(255,255,255,0.6)',
                      textAlign: 'center',
                      lineHeight: 1.3,
                      wordBreak: 'break-word',
                    }}
                  >
                    {item.name || 'Không xác định'}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Bảng chi tiết bên dưới */}
      <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: '20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Chi tiết theo phân vùng</h3>
        </div>
        <table style={{ border: 'none' }}>
          <thead>
            <tr>
              <th style={{ width: '40px', textAlign: 'center' }}>#</th>
              <th>Tên phân vùng</th>
              <th style={{ textAlign: 'right' }}>Số lượt nhận diện</th>
              <th style={{ textAlign: 'right' }}>Tỷ lệ phần trăm</th>
              <th style={{ textAlign: 'right' }}>Độ tin cậy TB</th>
            </tr>
          </thead>
          <tbody>
            {stats.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', padding: '30px', color: 'rgba(255,255,255,0.4)' }}>
                  Chưa có dữ liệu phân vùng
                </td>
              </tr>
            ) : (
              stats.map((item, idx) => {
                const percentage = totalCount > 0 ? (item.total_detections / totalCount) * 100 : 0;
                const color = BAR_COLORS[idx % BAR_COLORS.length];
                return (
                  <tr key={idx}>
                    <td style={{ textAlign: 'center' }}>
                      <div style={{ width: '10px', height: '10px', borderRadius: '2px', background: color, display: 'inline-block' }}></div>
                    </td>
                    <td style={{ fontWeight: 600 }}>
                      <i className="fa-solid fa-camera-retro" style={{ color, marginRight: '8px' }}></i>
                      {item.name || 'Không xác định'}
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 700 }}>{item.total_detections}</td>
                    <td style={{ textAlign: 'right', color: 'rgba(255,255,255,0.6)' }}>{percentage.toFixed(1)}%</td>
                    <td style={{ textAlign: 'right', color: item.avg_confidence >= 0.8 ? '#34d399' : '#fbbf24', fontWeight: 600 }}>
                      {item.avg_confidence > 0 ? `${(item.avg_confidence * 100).toFixed(1)}%` : '—'}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
