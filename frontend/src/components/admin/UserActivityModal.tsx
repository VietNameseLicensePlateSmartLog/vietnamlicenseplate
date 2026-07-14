'use client';

import { useState, useEffect, useCallback } from 'react';
import { API_BASE } from '@/lib/api';

interface ActivityItem {
  date: string;
  source_type: string;
  detection_count: number;
  avg_confidence: number;
}

interface UserActivityModalProps {
  isOpen: boolean;
  onClose: () => void;
  userId: number;
  username: string;
  email: string;
}

const SOURCE_LABELS: Record<string, { icon: string; label: string; color: string; bg: string }> = {
  image:    { icon: 'fa-solid fa-image',       label: 'Ảnh',    color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.15)' },
  video:    { icon: 'fa-solid fa-video',       label: 'Video',  color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.15)' },
  camera:   { icon: 'fa-solid fa-video',       label: 'Camera', color: '#a78bfa', bg: 'rgba(167, 139, 250, 0.15)' },
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  const day = d.getDate().toString().padStart(2, '0');
  const month = (d.getMonth() + 1).toString().padStart(2, '0');
  const year = d.getFullYear();
  const weekday = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'][d.getDay()];
  return `${weekday}, ${day}/${month}/${year}`;
}

export default function UserActivityModal({ isOpen, onClose, userId, username, email }: UserActivityModalProps) {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const LIMIT = 15;
  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  const fetchActivity = useCallback(async (skip: number) => {
    setIsLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/activity?skip=${skip}&limit=${LIMIT}`);
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Không thể tải lịch sử hoạt động.');
      }
      const data = await res.json();
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối.');
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  // Fetch khi mở modal hoặc chuyển trang
  useEffect(() => {
    if (isOpen) {
      fetchActivity(page * LIMIT);
    }
  }, [isOpen, page, fetchActivity]);

  // Reset page khi mở lại
  useEffect(() => {
    if (isOpen) setPage(0);
  }, [isOpen]);

  // Đóng bằng Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const getSourceInfo = (sourceType: string) => SOURCE_LABELS[sourceType] || { icon: 'fa-solid fa-circle-question', label: sourceType, color: '#94a3b8', bg: 'rgba(148,163,184,0.15)' };

  return (
    <div className="modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-content" style={{ maxWidth: '600px', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <h2 style={{ fontSize: '1.1rem', margin: 0 }}>
              <i className="fa-solid fa-clock-rotate-left" style={{ marginRight: '8px', color: '#60a5fa' }}></i>
              Lịch sử hoạt động
            </h2>
            <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)' }}>
              {username} — {email}
            </span>
          </div>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        {/* Body */}
        <div className="modal-body" style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
          {isLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
              <div className="spinner"></div>
            </div>
          ) : error ? (
            <div style={{ padding: '20px', color: '#fca5a5', textAlign: 'center' }}>
              <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '6px' }}></i>{error}
            </div>
          ) : items.length === 0 ? (
            <div style={{ padding: '40px 0', textAlign: 'center', color: 'rgba(255,255,255,0.4)' }}>
              <i className="fa-solid fa-inbox" style={{ fontSize: '2rem', display: 'block', marginBottom: '12px' }}></i>
              Chưa có hoạt động nhận diện nào.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              {items.map((item, idx) => {
                const src = getSourceInfo(item.source_type);
                const confPercent = (item.avg_confidence * 100).toFixed(1);
                return (
                  <div key={idx} style={{
                    display: 'flex', alignItems: 'center', gap: '12px',
                    padding: '10px 14px', borderRadius: '10px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.05)',
                    transition: 'background 0.15s',
                  }}>
                    {/* Ngày */}
                    <div style={{ flex: '0 0 auto', minWidth: '140px' }}>
                      <div style={{ fontSize: '0.85rem', fontWeight: 500, color: '#e2e8f0' }}>
                        {formatDate(item.date)}
                      </div>
                    </div>

                    {/* Badge nguồn */}
                    <div style={{
                      display: 'inline-flex', alignItems: 'center', gap: '5px',
                      padding: '3px 10px', borderRadius: '20px', fontSize: '0.75rem',
                      background: src.bg, border: `1px solid ${src.color}33`, color: src.color,
                      fontWeight: 600, whiteSpace: 'nowrap',
                    }}>
                      <i className={src.icon} style={{ fontSize: '0.7rem' }}></i>
                      {src.label}
                    </div>

                    {/* Số biển */}
                    <div style={{ flex: 1, textAlign: 'right' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#e2e8f0' }}>
                        {item.detection_count}
                      </span>
                      <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginLeft: '4px' }}>
                        biển số
                      </span>
                    </div>

                    {/* Confidence TB */}
                    <div style={{ flex: '0 0 auto', textAlign: 'right', minWidth: '70px' }}>
                      <span style={{
                        fontSize: '0.8rem', fontWeight: 600,
                        color: item.avg_confidence >= 0.8 ? '#34d399' : item.avg_confidence >= 0.6 ? '#fbbf24' : '#f87171',
                      }}>
                        {confPercent}%
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer — Pagination */}
        {total > LIMIT && (
          <div style={{
            display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px',
            padding: '12px 20px', borderTop: '1px solid rgba(255,255,255,0.08)',
          }}>
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              style={{
                padding: '5px 14px', borderRadius: '6px', fontSize: '0.8rem',
                background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
                color: page === 0 ? 'rgba(255,255,255,0.2)' : '#e2e8f0',
                cursor: page === 0 ? 'default' : 'pointer',
              }}
            >
              <i className="fa-solid fa-chevron-left" style={{ marginRight: '4px' }}></i>Trước
            </button>
            <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)' }}>
              Trang {page + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              style={{
                padding: '5px 14px', borderRadius: '6px', fontSize: '0.8rem',
                background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
                color: page >= totalPages - 1 ? 'rgba(255,255,255,0.2)' : '#e2e8f0',
                cursor: page >= totalPages - 1 ? 'default' : 'pointer',
              }}
            >
              Sau<i className="fa-solid fa-chevron-right" style={{ marginLeft: '4px' }}></i>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
