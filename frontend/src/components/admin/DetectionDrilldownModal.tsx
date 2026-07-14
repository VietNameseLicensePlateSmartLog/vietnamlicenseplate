'use client';

import { useState, useEffect, useCallback } from 'react';
import { API_BASE } from '@/lib/api';
import { getThumbnailUrl, formatVnTime } from '@/lib/utils';

interface DetectionItem {
  id: number;
  plate_text: string;
  plate_confidence: number;
  image_path: string;
  source_type: string;
  created_at: string;
  verified: number | null;
}

interface SearchResponse {
  total: number;
  items: DetectionItem[];
}

interface DetectionDrilldownModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  filterParams: {
    plate?: string;
    min_confidence?: number;
    max_confidence?: number;
  };
}

export default function DetectionDrilldownModal({ isOpen, onClose, title, filterParams }: DetectionDrilldownModalProps) {
  const [items, setItems] = useState<DetectionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const limit = 20;

  const fetchItems = useCallback(async (skip: number) => {
    try {
      setIsLoading(true);
      setError('');
      const params = new URLSearchParams();
      if (filterParams.plate) params.set('plate', filterParams.plate);
      if (filterParams.min_confidence !== undefined) params.set('min_confidence', String(filterParams.min_confidence));
      if (filterParams.max_confidence !== undefined) params.set('max_confidence', String(filterParams.max_confidence));
      params.set('skip', String(skip));
      params.set('limit', String(limit));

      const res = await fetch(`${API_BASE}/admin/detections/search?${params.toString()}`);
      if (!res.ok) throw new Error('Không thể tải dữ liệu.');
      const data: SearchResponse = await res.json();
      setItems(data.items);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối API.');
    } finally {
      setIsLoading(false);
    }
  }, [filterParams.plate, filterParams.min_confidence, filterParams.max_confidence]);

  useEffect(() => {
    if (isOpen) {
      setPage(0);
      fetchItems(0);
    }
  }, [isOpen, fetchItems]);

  const totalPages = Math.ceil(total / limit);

  const handlePrev = () => {
    if (page > 0) {
      const newPage = page - 1;
      setPage(newPage);
      fetchItems(newPage * limit);
    }
  };

  const handleNext = () => {
    if (page < totalPages - 1) {
      const newPage = page + 1;
      setPage(newPage);
      fetchItems(newPage * limit);
    }
  };

  // Đóng modal bằng Escape
  useEffect(() => {
    if (!isOpen) return;
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const sourceBadge = (source: string) => {
    const map: Record<string, { label: string; color: string; bg: string }> = {
      camera: { label: 'Camera', color: '#fbbf24', bg: 'rgba(251,191,36,0.15)' },
      video: { label: 'Video', color: '#34d399', bg: 'rgba(52,211,153,0.15)' },
      image: { label: 'Ảnh', color: '#60a5fa', bg: 'rgba(96,165,250,0.15)' },
    };
    const badge = map[source] || { label: source, color: '#94a3b8', bg: 'rgba(148,163,184,0.15)' };
    return (
      <span style={{ fontSize: '0.7rem', fontWeight: 600, color: badge.color, background: badge.bg, padding: '2px 8px', borderRadius: '4px' }}>
        {badge.label}
      </span>
    );
  };

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        style={{ background: '#1a1d2e', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.08)', width: '90vw', maxWidth: '1100px', maxHeight: '85vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 24px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>{title}</h2>
            <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)' }}>{total} kết quả</span>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'rgba(255,255,255,0.05)', border: 'none', color: 'rgba(255,255,255,0.6)', width: '32px', height: '32px', borderRadius: '8px', cursor: 'pointer', fontSize: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
          {isLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
              <div className="spinner"></div>
            </div>
          ) : error ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#ef4444' }}>
              <i className="fa-solid fa-triangle-exclamation" style={{ fontSize: '1.5rem', marginBottom: '10px', display: 'block' }}></i>
              {error}
            </div>
          ) : items.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: 'rgba(255,255,255,0.3)' }}>
              <i className="fa-solid fa-images" style={{ fontSize: '2.5rem', marginBottom: '12px', display: 'block' }}></i>
              Không có kết quả nào
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '16px' }}>
              {items.map(item => (
                <div key={item.id} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.06)', overflow: 'hidden', transition: 'border-color 0.2s' }}>
                  {/* Ảnh */}
                  <div style={{ height: '120px', background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                    <img
                      src={getThumbnailUrl(item.image_path)}
                      alt={item.plate_text || 'Snapshot'}
                      loading="lazy"
                      style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                    />
                  </div>
                  {/* Info */}
                  <div style={{ padding: '10px 12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.95rem', letterSpacing: '0.5px' }}>
                        {item.plate_text || 'N/A'}
                      </span>
                      {sourceBadge(item.source_type)}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.78rem', color: 'rgba(255,255,255,0.5)' }}>
                      <span style={{ color: item.plate_confidence >= 0.7 ? '#34d399' : item.plate_confidence >= 0.5 ? '#fbbf24' : '#ef4444', fontWeight: 600 }}>
                        {(item.plate_confidence * 100).toFixed(1)}%
                      </span>
                      <span>{formatVnTime(item.created_at)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer — Pagination */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '16px', padding: '16px 24px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
            <button
              onClick={handlePrev}
              disabled={page === 0}
              style={{ padding: '6px 16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: page === 0 ? 'transparent' : 'rgba(255,255,255,0.05)', color: page === 0 ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.8)', cursor: page === 0 ? 'default' : 'pointer', fontSize: '0.85rem' }}
            >
              <i className="fa-solid fa-chevron-left" style={{ marginRight: '6px' }}></i> Trước
            </button>
            <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)' }}>
              Trang {page + 1} / {totalPages}
            </span>
            <button
              onClick={handleNext}
              disabled={page >= totalPages - 1}
              style={{ padding: '6px 16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: page >= totalPages - 1 ? 'transparent' : 'rgba(255,255,255,0.05)', color: page >= totalPages - 1 ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.8)', cursor: page >= totalPages - 1 ? 'default' : 'pointer', fontSize: '0.85rem' }}
            >
              Sau <i className="fa-solid fa-chevron-right" style={{ marginLeft: '6px' }}></i>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
