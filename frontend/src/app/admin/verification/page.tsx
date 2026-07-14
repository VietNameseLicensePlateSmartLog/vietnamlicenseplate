'use client';

import { useState, useEffect } from 'react';
import { API_BASE } from '@/lib/api';
import { formatVnTime } from '@/lib/utils';
import { getThumbnailUrl } from '@/lib/utils';

interface UnverifiedDetection {
  id: number;
  plate_text: string;
  plate_confidence: number;
  alt_text: string | null;
  alt_confidence: number | null;
  total_frames: number | null;
  image_path: string;
  source_type: string;
  created_at: string;
}

export default function Verification() {
  const [items, setItems] = useState<UnverifiedDetection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<{ [key: number]: boolean }>({});

  const fetchUnverified = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE}/admin/detections/unverified?limit=20`);
      if (!res.ok) {
        throw new Error('Không thể tải danh sách biển số chưa xác minh.');
      }
      const data = await res.json();
      setItems(data);
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối API.');
    } finally {
      setIsLoading(false);
    }
  };

  /** Fetch 1 unverified detection tiếp theo để thay thế item vừa xác minh/xóa */
  const fetchNextItem = async (currentCount: number) => {
    try {
      const res = await fetch(`${API_BASE}/admin/detections/unverified?skip=${currentCount}&limit=1`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.length > 0) {
        setItems(prev => {
          // Tránh duplicate key — chỉ thêm nếu id chưa có trong danh sách
          if (prev.some(item => item.id === data[0].id)) return prev;
          return [...prev, data[0]];
        });
      }
    } catch { /* silent — không làm gián đoạn UI */ }
  };

  useEffect(() => {
    fetchUnverified();
  }, []);

  const handleVerify = async (id: number, isCorrect: number, correctPlate: string) => {
    setActionLoading(prev => ({ ...prev, [id]: true }));
    try {
      const userId = localStorage.getItem('userId') || '0';
      const url = `${API_BASE}/admin/verify-detection?detection_id=${id}&correct_plate=${encodeURIComponent(correctPlate)}&is_correct=${isCorrect}&verified_by=${userId}`;

      const res = await fetch(url, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Lỗi khi xác minh.');
      }

      setItems(prev => {
        const next = prev.filter(item => item.id !== id);
        fetchNextItem(next.length);
        return next;
      });
    } catch (err: any) {
      alert(err.message || 'Đã xảy ra lỗi.');
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: false }));
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Bạn có chắc muốn xóa bản ghi nhận diện này?')) return;

    setActionLoading(prev => ({ ...prev, [id]: true }));
    try {
      const res = await fetch(`${API_BASE}/admin/detections/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Lỗi khi xóa.');
      }
      setItems(prev => {
        const next = prev.filter(item => item.id !== id);
        fetchNextItem(next.length);
        return next;
      });
    } catch (err: any) {
      alert(err.message || 'Đã xảy ra lỗi.');
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: false }));
    }
  };

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
          <h1 style={{ fontSize: '1.8rem', fontWeight: 600 }}>Xác minh kết quả nhận diện</h1>
          <p style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.9rem' }}>Đánh giá đúng/sai kết quả nhận diện biển số của mô hình AI</p>
        </div>
        <button onClick={fetchUnverified} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <i className="fa-solid fa-rotate"></i> Tải lại
        </button>
      </div>

      {error && (
        <div className="card" style={{ padding: '20px', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#fca5a5', marginBottom: '20px' }}>
          <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '8px' }}></i> {error}
        </div>
      )}

      {items.length === 0 ? (
        <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'rgba(255,255,255,0.6)' }}>
          <i className="fa-solid fa-circle-check" style={{ fontSize: '3rem', color: '#10b981', marginBottom: '15px' }}></i>
          <h3>Tất cả đã được xác minh!</h3>
          <p style={{ fontSize: '0.9rem', marginTop: '5px' }}>Không còn bản ghi nhận diện nào cần duyệt lúc này.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
          {items.map(item => {
            const formattedTime = formatVnTime(item.created_at);
            const isSaving = actionLoading[item.id];

            return (
              <div key={item.id} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '15px', padding: '15px' }}>

                {/* Ảnh snapshot */}
                <div style={{ position: 'relative', width: '100%', height: '180px', borderRadius: '8px', overflow: 'hidden', background: '#000', display: 'flex', justifyContent: 'center', alignItems: 'center', border: '1px solid rgba(255,255,255,0.05)' }}>
                  {item.image_path ? (
                    <img
                      loading="lazy"
                      src={getThumbnailUrl(item.image_path)}
                      alt="License Plate Crop"
                      style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                    />
                  ) : (
                    <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.3)' }}>Không có ảnh</span>
                  )}
                  <span style={{ position: 'absolute', top: '10px', left: '10px', padding: '4px 8px', borderRadius: '4px', background: 'rgba(0,0,0,0.6)', fontSize: '0.75rem', textTransform: 'capitalize' }}>
                    {item.source_type}
                  </span>
                </div>

                {/* Chi tiết AI */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                    <span style={{ color: 'rgba(255,255,255,0.5)' }}>Thời gian:</span>
                    <span>{formattedTime}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.9rem' }}>AI dự đoán:</span>
                    <span style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 8px', borderRadius: '4px', fontWeight: 700, letterSpacing: '1px' }}>
                      {item.plate_text}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                    <span style={{ color: 'rgba(255,255,255,0.5)' }}>Độ tin cậy:</span>
                    <span style={{ color: item.plate_confidence >= 0.8 ? '#34d399' : '#fbbf24', fontWeight: 600 }}>
                      {(item.plate_confidence * 100).toFixed(2)}%
                    </span>
                  </div>
                  {item.alt_text && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', background: 'rgba(255,255,255,0.04)', padding: '6px 10px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.75rem' }}>Đọc thay thế (ver 2)</span>
                        <span style={{ color: 'rgba(255,255,255,0.75)', fontWeight: 600, letterSpacing: '1px' }}>
                          {item.alt_text}
                          <span style={{ color: (item.alt_confidence || 0) >= 0.8 ? '#34d399' : '#fbbf24', fontWeight: 500, marginLeft: '6px', fontSize: '0.8rem' }}>
                            {((item.alt_confidence || 0) * 100).toFixed(2)}%
                          </span>
                        </span>
                      </div>
                    </div>
                  )}
                  {item.total_frames && item.total_frames > 1 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span style={{ color: 'rgba(255,255,255,0.5)' }}>Số frame:</span>
                      <span style={{ color: 'rgba(255,255,255,0.6)' }}>{item.total_frames} frame</span>
                    </div>
                  )}
                </div>

                {/* Nút xác minh */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                  {/* Nút Đúng / Sai — dùng plate_text chính */}
                  <div style={{ display: 'grid', gridTemplateColumns: item.alt_text ? '1fr 1fr 1fr' : '1fr 1fr 1fr', gap: '10px' }}>
                    <button
                      onClick={() => handleVerify(item.id, 1, item.plate_text)}
                      disabled={isSaving}
                      style={{
                        backgroundColor: '#10b981',
                        color: '#fff',
                        opacity: isSaving ? 0.5 : 1,
                        cursor: isSaving ? 'not-allowed' : 'pointer'
                      }}
                    >
                      {isSaving ? <i className="fa-solid fa-circle-notch fa-spin"></i> : <><i className="fa-solid fa-check" style={{ marginRight: '5px' }}></i>Đúng</>}
                    </button>
                    <button
                      onClick={() => handleVerify(item.id, 0, item.plate_text)}
                      disabled={isSaving}
                      style={{
                        backgroundColor: 'rgba(245, 158, 11, 0.2)',
                        border: '1px solid rgba(245, 158, 11, 0.4)',
                        color: '#fbc02d',
                        opacity: isSaving ? 0.5 : 1,
                        cursor: isSaving ? 'not-allowed' : 'pointer'
                      }}
                    >
                      {isSaving ? <i className="fa-solid fa-circle-notch fa-spin"></i> : <><i className="fa-solid fa-xmark" style={{ marginRight: '5px' }}></i>Sai</>}
                    </button>
                    <button
                      onClick={() => handleDelete(item.id)}
                      disabled={isSaving}
                      style={{
                        backgroundColor: 'rgba(239, 68, 68, 0.2)',
                        border: '1px solid rgba(239, 68, 68, 0.4)',
                        color: '#f87171',
                        opacity: isSaving ? 0.5 : 1,
                        cursor: isSaving ? 'not-allowed' : 'pointer'
                      }}
                    >
                      {isSaving ? <i className="fa-solid fa-circle-notch fa-spin"></i> : <><i className="fa-solid fa-trash" style={{ marginRight: '5px' }}></i>Xóa</>}
                    </button>
                  </div>

                  {/* Nút "Dùng ver alt" — chỉ hiện khi có alt_text */}
                  {item.alt_text && (
                    <button
                      onClick={() => handleVerify(item.id, 1, item.alt_text!)}
                      disabled={isSaving}
                      style={{
                        width: '100%',
                        background: 'rgba(99,102,241,0.2)',
                        border: '1px solid rgba(99,102,241,0.4)',
                        color: '#a5b4fc',
                        padding: '8px',
                        borderRadius: '6px',
                        fontSize: '0.85rem',
                        fontWeight: 500,
                        cursor: isSaving ? 'not-allowed' : 'pointer',
                        opacity: isSaving ? 0.5 : 1,
                      }}
                    >
                      <i className="fa-solid fa-arrow-right-arrow-left" style={{ marginRight: '6px', fontSize: '0.8rem' }}></i>
                      Dùng ver thay thế: <strong>{item.alt_text}</strong>
                    </button>
                  )}
                </div>

              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
