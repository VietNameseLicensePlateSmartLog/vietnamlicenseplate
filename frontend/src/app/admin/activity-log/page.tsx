'use client';

import { useState, useEffect } from 'react';
import { API_BASE } from '@/lib/api';
import { formatVnTime } from '@/lib/utils';

interface ActivityLog {
  id: number;
  user_email: string | null;
  action: string;
  detail: string;
  ip_address: string | null;
  created_at: string;
}

export default function ActivityLog() {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchLogs = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE}/admin/activity-logs?limit=200`);
      if (!res.ok) {
        throw new Error('Không thể tải nhật ký hoạt động.');
      }
      const data = await res.json();
      setLogs(data);
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối API.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flex: 1, justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 600 }}>Nhật ký hoạt động</h1>
          <p style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.9rem' }}>Xem toàn bộ lịch sử thao tác và sự kiện hệ thống</p>
        </div>
        <button onClick={fetchLogs} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <i className="fa-solid fa-rotate"></i> Tải lại
        </button>
      </div>

      {error && (
        <div className="card" style={{ padding: '20px', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#fca5a5', marginBottom: '20px' }}>
          <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '8px' }}></i> {error}
        </div>
      )}

      <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
        <div className="table-scroll-container">
          <table style={{ minWidth: '800px' }}>
            <thead>
              <tr>
                <th style={{ width: '200px' }}>Email</th>
                <th style={{ width: '200px' }}>Hành động</th>
                <th>Chi tiết sự kiện</th>
                <th style={{ width: '150px' }}>Địa chỉ IP</th>
                <th style={{ width: '180px' }}>Thời gian ghi nhận</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '30px', color: 'rgba(255,255,255,0.4)' }}>
                    Không có nhật ký hoạt động nào
                  </td>
                </tr>
              ) : (
                logs.map(log => {
                  const formattedTime = formatVnTime(log.created_at);

                  // Phân biệt màu sắc dựa trên hành động
                  let actionColor = '#fff';
                  if (log.action.toLowerCase().includes('login') || log.action.toLowerCase().includes('đăng nhập')) {
                    actionColor = '#60a5fa';
                  } else if (log.action.toLowerCase().includes('block') || log.action.toLowerCase().includes('chặn') || log.action.toLowerCase().includes('khóa')) {
                    actionColor = '#fca5a5';
                  } else if (log.action.toLowerCase().includes('verify') || log.action.toLowerCase().includes('xác minh')) {
                    actionColor = '#34d399';
                  }

                  return (
                    <tr key={log.id}>
                      <td>
                        <span style={{ fontWeight: 600 }}>
                          {log.user_email || 'Hệ thống'}
                        </span>
                      </td>
                      <td>
                        <span style={{ color: actionColor, fontWeight: 600 }}>
                          {log.action}
                        </span>
                      </td>
                      <td style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.9rem' }}>{log.detail}</td>
                      <td style={{ fontFamily: 'monospace', color: 'rgba(255,255,255,0.6)' }}>{log.ip_address || 'N/A'}</td>
                      <td>{formattedTime}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
