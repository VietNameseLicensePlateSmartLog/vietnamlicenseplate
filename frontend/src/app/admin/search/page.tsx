'use client';

import { useState, useEffect } from 'react';
import { API_BASE } from '@/lib/api';
import { formatVnTime } from '@/lib/utils';

interface SearchResult {
  id: number;
  plate_text: string;
  plate_confidence: number;
  alt_text: string | null;
  alt_confidence: number | null;
  total_frames: number | null;
  image_path: string;
  source_type: string;
  region_id: number | null;
  created_at: string;
}

export default function SearchDetections() {
  const [plate, setPlate] = useState('');
  const [sourceType, setSourceType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [verified, setVerified] = useState('');
  const [regions, setRegions] = useState<{ id: number; name: string }[]>([]);
  const [selectedRegionId, setSelectedRegionId] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedImg, setSelectedImg] = useState<string | null>(null);

  const fetchRegions = async () => {
    try {
      const res = await fetch(`${API_BASE}/regions`);
      if (res.ok) {
        const data = await res.json();
        setRegions(data);
      }
    } catch (err) {
      console.error('Không thể tải phân vùng:', err);
    }
  };

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const params = new URLSearchParams();
      if (plate) params.append('plate', plate.trim());
      if (sourceType) params.append('source_type', sourceType);
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);
      if (verified) params.append('verified', verified);
      if (selectedRegionId) params.append('region_id', selectedRegionId);

      const res = await fetch(`${API_BASE}/admin/detections/search?${params.toString()}`);
      if (!res.ok) {
        throw new Error('Lỗi khi truy vấn dữ liệu.');
      }
      const data = await res.json();
      setResults(data);
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối API.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setPlate('');
    setSourceType('');
    setDateFrom('');
    setDateTo('');
    setVerified('');
    setSelectedRegionId('');
    setResults([]);
  };

  useEffect(() => {
    // Tải dữ liệu mặc định ban đầu
    fetchRegions();
    handleSearch();
  }, []);

  return (
    <>
      <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 600 }}>Tra cứu dữ liệu biển số nâng cao</h1>
        <p style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.9rem', marginBottom: '20px' }}>Tìm kiếm lịch sử xe và lọc thông tin nhận diện nâng cao từ cơ sở dữ liệu</p>
      </div>

      {/* Bộ lọc tìm kiếm */}
      <div className="card" style={{ padding: '20px', marginBottom: '20px' }}>
        <form onSubmit={handleSearch}>
          <div className="form-grid">
            <div className="form-group">
              <label><i className="fa-solid fa-credit-card" style={{ color: 'var(--primary)' }}></i> Biển số xe</label>
              <input 
                type="text" 
                value={plate} 
                onChange={(e) => setPlate(e.target.value.toUpperCase())}
                placeholder="VD: 29A12345..."
              />
            </div>

            <div className="form-group">
              <label><i className="fa-solid fa-network-wired" style={{ color: 'var(--primary)' }}></i> Nguồn nhận diện</label>
              <select 
                value={sourceType} 
                onChange={(e) => setSourceType(e.target.value)}
              >
                <option value="" style={{ background: '#1c2230' }}>Tất cả nguồn</option>
                <option value="image" style={{ background: '#1c2230' }}>Ảnh tải lên</option>
                <option value="video" style={{ background: '#1c2230' }}>Video tải lên</option>
                <option value="camera" style={{ background: '#1c2230' }}>Camera trực tuyến</option>
              </select>
            </div>

            <div className="form-group">
              <label><i className="fa-solid fa-map-location-dot" style={{ color: 'var(--primary)' }}></i> Vị trí Camera (Phân vùng)</label>
              <select 
                value={selectedRegionId} 
                onChange={(e) => setSelectedRegionId(e.target.value)}
              >
                <option value="" style={{ background: '#1c2230' }}>Tất cả vị trí</option>
                {regions.map((reg) => (
                  <option key={reg.id} value={reg.id} style={{ background: '#1c2230' }}>
                    {reg.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label><i className="fa-solid fa-user-check" style={{ color: 'var(--primary)' }}></i> Trạng thái xác minh</label>
              <select 
                value={verified} 
                onChange={(e) => setVerified(e.target.value)}
              >
                <option value="" style={{ background: '#1c2230' }}>Tất cả trạng thái</option>
                <option value="yes" style={{ background: '#1c2230' }}>Đã xác minh</option>
                <option value="no" style={{ background: '#1c2230' }}>Chưa xác minh</option>
              </select>
            </div>

            <div className="form-group">
              <label><i className="fa-solid fa-calendar-day" style={{ color: 'var(--primary)' }}></i> Từ ngày</label>
              <input 
                type="date" 
                value={dateFrom} 
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label><i className="fa-solid fa-calendar-day" style={{ color: 'var(--primary)' }}></i> Đến ngày</label>
              <input 
                type="date" 
                value={dateTo} 
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
          </div>

          <div className="form-actions" style={{ marginTop: '20px', justifyContent: 'flex-end' }}>
            <button type="submit" disabled={isLoading} style={{ width: '130px', flex: 'none' }}>
              <i className="fa-solid fa-magnifying-glass"></i> Tìm kiếm
            </button>
            <button type="button" onClick={handleReset} className="btn-secondary" style={{ width: '130px', flex: 'none' }}>
              Xóa bộ lọc
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="card" style={{ padding: '20px', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#fca5a5', marginBottom: '20px' }}>
          <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '8px' }}></i> {error}
        </div>
      )}

      {/* Kết quả tìm kiếm */}
      <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
        <div className="table-scroll-container">
          <table style={{ minWidth: '850px' }}>
            <thead>
              <tr>
                <th style={{ width: '80px' }}>ID</th>
                <th style={{ width: '120px' }}>Ảnh chụp</th>
                <th>Biển số xe</th>
                <th>Độ tin cậy</th>
                <th>Nguồn</th>
                <th>Vị trí Camera</th>
                <th>Thời gian nhận diện</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '40px' }}>
                    <div className="spinner"></div>
                  </td>
                </tr>
              ) : results.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '30px', color: 'rgba(255,255,255,0.4)' }}>
                    Không có kết quả tìm kiếm nào phù hợp
                  </td>
                </tr>
              ) : (
                results.map(item => {
                  const formattedTime = formatVnTime(item.created_at);
                  return (
                    <tr key={item.id}>
                      <td style={{ color: 'rgba(255,255,255,0.4)' }}>#{item.id}</td>
                      <td>
                        {item.image_path ? (
                          <div 
                            style={{ width: '80px', height: '45px', borderRadius: '4px', overflow: 'hidden', background: '#000', border: '1px solid rgba(255,255,255,0.1)', cursor: 'zoom-in' }}
                            onClick={() => setSelectedImg(item.image_path)}
                            title="Bấm để xem ảnh lớn"
                          >
                            <img src={item.image_path} alt="Thumb" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          </div>
                        ) : (
                          <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.3)' }}>Không có ảnh</span>
                        )}
                      </td>
                      <td>
                        <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '1.05rem', letterSpacing: '1px', background: 'rgba(255,255,255,0.05)', padding: '3px 8px', borderRadius: '4px' }}>
                          {item.plate_text}
                        </span>
                        {item.alt_text && (
                          <div style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.4)', marginTop: '3px', fontStyle: 'italic' }}>
                            Alt: {item.alt_text} ({((item.alt_confidence || 0) * 100).toFixed(2)}%)
                          </div>
                        )}
                      </td>
                      <td style={{ color: item.plate_confidence >= 0.8 ? '#34d399' : '#fbbf24', fontWeight: 600 }}>
                        {(item.plate_confidence * 100).toFixed(2)}%
                      </td>
                      <td style={{ textTransform: 'capitalize' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                          {item.source_type === 'image' && <><i className="fa-regular fa-image" style={{ color: '#60a5fa' }}></i> Ảnh</>}
                          {item.source_type === 'video' && <><i className="fa-regular fa-file-video" style={{ color: '#a7f3d0' }}></i> Video</>}
                          {item.source_type === 'camera' && <><i className="fa-solid fa-video" style={{ color: '#fbbf24' }}></i> Camera</>}
                        </span>
                      </td>
                      <td>
                        <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.9rem' }}>
                          {item.region_id 
                            ? (regions.find(r => r.id === item.region_id)?.name || `Phân vùng #${item.region_id}`)
                            : 'Mặc định'}
                        </span>
                      </td>
                      <td>{formattedTime}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Lightbox hiển thị ảnh lớn */}
      {selectedImg && (
        <div 
          style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.85)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000, cursor: 'zoom-out' }}
          onClick={() => setSelectedImg(null)}
        >
          <div style={{ position: 'relative', maxWidth: '85vw', maxHeight: '85vh' }}>
            <img src={selectedImg} alt="Plate Snapshot Full" style={{ width: '100%', height: '100%', objectFit: 'contain', borderRadius: '8px', boxShadow: '0 10px 30px rgba(0,0,0,0.5)' }} />
            <button 
              onClick={() => setSelectedImg(null)}
              style={{ position: 'absolute', top: '-40px', right: '0', background: 'none', border: 'none', color: '#fff', fontSize: '1.5rem', cursor: 'pointer' }}
            >
              <i className="fa-solid fa-xmark"></i> Đóng
            </button>
          </div>
        </div>
      )}
    </>
  );
}
