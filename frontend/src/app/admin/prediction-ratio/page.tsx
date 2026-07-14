'use client';

import { useState, useEffect } from 'react';
import { API_BASE } from '@/lib/api';
import { formatVnTime, getThumbnailUrl } from '@/lib/utils';

interface StatsData {
  total_verified: number;
  correct: number;
  incorrect: number;
  accuracy: number;
}

interface IncorrectDetection {
  detection_id: number;
  predicted_text: string;
  correct_plate: string;
  image_path: string;
  source_type: string;
  plate_confidence: number;
  verified_at: string;
}

export default function PredictionRatio() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [incorrectList, setIncorrectList] = useState<IncorrectDetection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE}/admin/stats`);
      if (!res.ok) {
        throw new Error('Không thể tải số liệu thống kê.');
      }
      const data = await res.json();
      setStats({
        total_verified: data.total_verified,
        correct: data.correct,
        incorrect: data.incorrect,
        accuracy: data.accuracy
      });
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối API.');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchIncorrect = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/detections/incorrect?limit=50`);
      if (!res.ok) return;
      const data = await res.json();
      setIncorrectList(data);
    } catch { /* silent */ }
  };

  const handleDeleteIncorrect = async (detectionId: number) => {
    if (!confirm('Bạn có chắc muốn xóa bản ghi nhận diện này?')) return;
    try {
      const res = await fetch(`${API_BASE}/admin/detections/${detectionId}`, { method: 'DELETE' });
      if (!res.ok) return;
      setIncorrectList(prev => prev.filter(item => item.detection_id !== detectionId));
      // Cập nhật lại stats
      fetchStats();
    } catch { /* silent */ }
  };

  useEffect(() => {
    fetchStats();
    fetchIncorrect();
  }, []);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flex: 1, justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="card" style={{ padding: '30px', textAlign: 'center', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
        <i className="fa-solid fa-triangle-exclamation" style={{ fontSize: '2rem', color: '#ef4444', marginBottom: '15px' }}></i>
        <h3 style={{ marginBottom: '10px' }}>Lỗi tải dữ liệu</h3>
        <p style={{ color: 'rgba(255, 255, 255, 0.7)', marginBottom: '20px' }}>{error}</p>
        <button onClick={fetchStats}>Thử lại</button>
      </div>
    );
  }

  const correctPercent = stats.total_verified > 0 ? (stats.correct / stats.total_verified) * 100 : 0;
  const incorrectPercent = stats.total_verified > 0 ? (stats.incorrect / stats.total_verified) * 100 : 0;

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 600 }}>Tỷ lệ dự đoán của AI</h1>
          <p style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.9rem' }}>Đo lường độ chính xác nhận diện biển số xe qua xác minh thủ công</p>
        </div>
        <button onClick={fetchStats} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <i className="fa-solid fa-rotate"></i> Cập nhật
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
        {/* Vòng tròn phần trăm chính xác */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px', gap: '20px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'rgba(255,255,255,0.8)' }}>Độ chính xác trung bình</h3>
          
          <div style={{ position: 'relative', width: '180px', height: '180px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <svg style={{ transform: 'rotate(-90deg)', width: '100%', height: '100%' }}>
              <circle 
                cx="90" cy="90" r="75" 
                style={{ fill: 'none', stroke: 'rgba(255,255,255,0.05)', strokeWidth: '12' }}
              />
              <circle 
                cx="90" cy="90" r="75" 
                style={{ 
                  fill: 'none', 
                  stroke: 'url(#gradient)', 
                  strokeWidth: '12',
                  strokeDasharray: '471',
                  strokeDashoffset: 471 - (471 * stats.accuracy) / 100,
                  strokeLinecap: 'round',
                  transition: 'stroke-dashoffset 1s ease-in-out'
                }}
              />
              <defs>
                <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="var(--primary)" />
                  <stop offset="100%" stopColor="#818cf8" />
                </linearGradient>
              </defs>
            </svg>
            <div style={{ position: 'absolute', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ fontSize: '2.2rem', fontWeight: 800, color: '#fff' }}>{stats.accuracy}%</span>
              <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)' }}>Chính xác</span>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', width: '100%', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '20px', marginTop: '10px' }}>
            <div style={{ textAlign: 'center' }}>
              <span style={{ display: 'block', fontSize: '0.75rem', color: 'rgba(255,255,255,0.5)' }}>Tổng đã duyệt</span>
              <span style={{ fontSize: '1.2rem', fontWeight: 700 }}>{stats.total_verified}</span>
            </div>
            <div style={{ borderLeft: '1px solid rgba(255,255,255,0.1)', height: '35px' }}></div>
            <div style={{ textAlign: 'center' }}>
              <span style={{ display: 'block', fontSize: '0.75rem', color: 'rgba(255,255,255,0.5)' }}>Đúng</span>
              <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#34d399' }}>{stats.correct}</span>
            </div>
            <div style={{ borderLeft: '1px solid rgba(255,255,255,0.1)', height: '35px' }}></div>
            <div style={{ textAlign: 'center' }}>
              <span style={{ display: 'block', fontSize: '0.75rem', color: 'rgba(255,255,255,0.5)' }}>Sai</span>
              <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fca5a5' }}>{stats.incorrect}</span>
            </div>
          </div>
        </div>

        {/* Thanh tỉ lệ & Đánh giá chi tiết */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '30px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Tỷ lệ phân phối</h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem' }}>
                <span>Nhận diện đúng (True Positive)</span>
                <span style={{ color: '#34d399', fontWeight: 600 }}>{correctPercent.toFixed(1)}%</span>
              </div>
              <div style={{ height: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', overflow: 'hidden' }}>
                <div style={{ height: '100%', background: '#10b981', width: `${correctPercent}%`, borderRadius: '6px' }}></div>
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem' }}>
                <span>Nhận diện sai (False Positive / False Negative)</span>
                <span style={{ color: '#fca5a5', fontWeight: 600 }}>{incorrectPercent.toFixed(1)}%</span>
              </div>
              <div style={{ height: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', overflow: 'hidden' }}>
                <div style={{ height: '100%', background: '#ef4444', width: `${incorrectPercent}%`, borderRadius: '6px' }}></div>
              </div>
            </div>
          </div>

          <div style={{ marginTop: '10px', background: 'rgba(255,255,255,0.02)', padding: '15px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', fontSize: '0.9rem', color: 'rgba(255,255,255,0.7)', lineHeight: '1.5' }}>
            <h4 style={{ color: '#fff', fontSize: '0.95rem', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <i className="fa-solid fa-lightbulb" style={{ color: '#fbbf24' }}></i> Ý nghĩa chỉ số
            </h4>
            <p style={{ marginBottom: '8px' }}>
              - <strong>Tỷ lệ đúng</strong> thể hiện khả năng định vị chính xác biển số xe và phân loại/đọc ký tự biển số hoàn toàn chính xác của mô hình YOLOv8.
            </p>
            <p>
              - <strong>Tỷ lệ sai</strong> ghi nhận các trường hợp biển số bị mờ, lóa sáng, góc khuất, hoặc lỗi nhận diện ký tự (ví dụ: nhầm 8 thành B, 0 thành D). Dữ liệu này giúp tối ưu hóa và huấn luyện lại mô hình tốt hơn trong tương lai.
            </p>
          </div>
        </div>
      </div>

      {/* Danh sách biển số nhận diện sai */}
      <div style={{ marginTop: '25px' }}>
        <h2 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <i className="fa-solid fa-circle-xmark" style={{ color: '#ef4444' }}></i>
          Biển số nhận diện sai
          {incorrectList.length > 0 && (
            <span style={{ fontSize: '0.8rem', fontWeight: 500, color: '#fca5a5', background: 'rgba(239,68,68,0.15)', padding: '2px 10px', borderRadius: '12px' }}>
              {incorrectList.length}
            </span>
          )}
        </h2>

        {incorrectList.length === 0 ? (
          <div className="card" style={{ padding: '30px', textAlign: 'center', color: 'rgba(255,255,255,0.5)' }}>
            <i className="fa-solid fa-circle-check" style={{ fontSize: '1.5rem', color: '#10b981', marginBottom: '10px' }}></i>
            <p>Chưa có biển số nào bị nhận diện sai. Hãy quay lại trang <strong>Xác minh</strong> để duyệt kết quả.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {incorrectList.map((item) => (
              <div key={item.detection_id} className="card" style={{ display: 'flex', alignItems: 'center', gap: '18px', padding: '14px 18px' }}>
                {/* Ảnh snapshot — click để phóng to */}
                <div
                  onClick={() => item.image_path && setPreviewImage(item.image_path)}
                  style={{ width: '120px', height: '75px', borderRadius: '8px', overflow: 'hidden', background: '#000', flexShrink: 0, border: '1px solid rgba(255,255,255,0.05)', cursor: item.image_path ? 'pointer' : 'default' }}
                >
                  {item.image_path ? (
                    <img
                      loading="lazy"
                      src={getThumbnailUrl(item.image_path)}
                      alt="Snapshot"
                      style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                    />
                  ) : (
                    <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', color: 'rgba(255,255,255,0.3)' }}>
                      Không có ảnh
                    </div>
                  )}
                </div>

                {/* Thông tin */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.9rem' }}>
                    <span style={{ color: 'rgba(255,255,255,0.5)' }}>AI dự đoán:</span>
                    <span style={{ fontWeight: 700, letterSpacing: '1px', color: '#fca5a5', textDecoration: 'line-through' }}>
                      {item.predicted_text}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.9rem' }}>
                    <span style={{ color: 'rgba(255,255,255,0.5)' }}>Đúng là:</span>
                    <span style={{ fontWeight: 700, letterSpacing: '1px', color: '#34d399' }}>
                      {item.correct_plate}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: '0.8rem', color: 'rgba(255,255,255,0.4)' }}>
                    <span>
                      <i className="fa-solid fa-camera" style={{ marginRight: '4px' }}></i>
                      {item.source_type}
                    </span>
                    <span>
                      <i className="fa-solid fa-circle-check" style={{ marginRight: '4px' }}></i>
                      {(item.plate_confidence * 100).toFixed(1)}%
                    </span>
                    {item.verified_at && (
                      <span>
                        <i className="fa-solid fa-clock" style={{ marginRight: '4px' }}></i>
                        {formatVnTime(item.verified_at)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Nút xóa */}
                <div
                  onClick={() => handleDeleteIncorrect(item.detection_id)}
                  style={{ flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', width: '36px', height: '36px', borderRadius: '50%', background: 'rgba(239,68,68,0.15)', cursor: 'pointer', transition: 'background 0.2s' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.3)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.15)')}
                >
                  <i className="fa-solid fa-xmark" style={{ color: '#ef4444', fontSize: '1rem' }}></i>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal xem ảnh phóng to */}
      {previewImage && (
        <div
          onClick={() => setPreviewImage(null)}
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.85)',
            display: 'flex', justifyContent: 'center', alignItems: 'center',
            cursor: 'pointer'
          }}
        >
          <div style={{ position: 'relative', maxWidth: '90vw', maxHeight: '90vh' }}>
            <img
              src={previewImage}
              alt="Preview"
              style={{ maxWidth: '90vw', maxHeight: '90vh', objectFit: 'contain', borderRadius: '8px' }}
            />
            <div
              onClick={() => setPreviewImage(null)}
              style={{
                position: 'absolute', top: '-12px', right: '-12px',
                width: '32px', height: '32px', borderRadius: '50%',
                background: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer', fontSize: '0.9rem', color: '#fff'
              }}
            >
              <i className="fa-solid fa-xmark"></i>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
