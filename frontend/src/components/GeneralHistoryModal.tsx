'use client';

import { useState, useEffect } from 'react';
import { API_BASE } from '@/lib/api';

interface HistoryItem {
  id: number;
  plate_text: string;
  plate_confidence: number;
  image_path: string | null;
  created_at: string;
}

interface GeneralHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function GeneralHistoryModal({ isOpen, onClose }: GeneralHistoryModalProps) {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<HistoryItem | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchHistory = async () => {
    setIsLoading(true);
    setError('');
    try {
      const userId = localStorage.getItem('userId');
      const userRole = localStorage.getItem('userRole');
      
      let url = `${API_BASE}/history?limit=100`;
      if (userId && userRole !== 'admin') {
        url += `&user_id=${userId}`;
      }

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error('Không thể tải lịch sử từ máy chủ.');
      }
      const data = await response.json();
      setHistory(data);
      if (data.length > 0) {
        setSelectedItem(data[0]); // Select first item by default
      } else {
        setSelectedItem(null);
      }
    } catch (err: any) {
      setError(err.message || 'Có lỗi xảy ra.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchHistory();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Avoid selecting the row
    if (!confirm('Bạn có chắc chắn muốn xóa bản ghi lịch sử này?')) return;

    try {
      const response = await fetch(`${API_BASE}/history/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error('Xóa bản ghi thất bại.');
      }
      
      // Update local state
      setHistory((prev) => {
        const updated = prev.filter((item) => item.id !== id);
        // If deleted the currently selected item, select the next one or null
        if (selectedItem?.id === id) {
          setSelectedItem(updated.length > 0 ? updated[0] : null);
        }
        return updated;
      });
    } catch (err: any) {
      alert(err.message || 'Lỗi khi xóa.');
    }
  };

  return (
    <div className="modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-content" style={{ maxWidth: '900px', width: '95%', height: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-header">
          <h2>Lịch sử nhận diện tổng quát</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        
        <div className="modal-body" style={{ flex: 1, display: 'flex', overflow: 'hidden', padding: 0 }}>
          {isLoading ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '1rem', color: 'var(--text-secondary)' }}>
              <div className="spinner"></div>
              <span>Đang tải lịch sử nhận diện...</span>
            </div>
          ) : error ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--danger)', padding: '2rem', textAlign: 'center' }}>
              <div>
                <i className="fa-solid fa-triangle-exclamation" style={{ fontSize: '2rem', marginBottom: '1rem' }}></i>
                <p>{error}</p>
                <button className="btn btn-primary mt-3" onClick={fetchHistory}>Thử lại</button>
              </div>
            </div>
          ) : history.length === 0 ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
              <i className="fa-regular fa-folder-open" style={{ fontSize: '3rem', marginBottom: '1rem' }}></i>
              <span>Chưa có lịch sử nhận diện nào được lưu trữ.</span>
            </div>
          ) : (
            <div style={{ display: 'flex', width: '100%', height: '100%' }}>
              {/* Left Panel: List */}
              <div style={{ width: '55%', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div style={{ overflowY: 'auto', flex: 1 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--bg-secondary)', zIndex: 1, borderBottom: '1px solid var(--border-color)' }}>
                      <tr>
                        <th style={{ padding: '0.8rem 1rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Biển số</th>
                        <th style={{ padding: '0.8rem 1rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Độ tin cậy</th>
                        <th style={{ padding: '0.8rem 1rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Thời gian</th>
                        <th style={{ padding: '0.8rem 1rem', fontSize: '0.85rem', color: 'var(--text-secondary)', textAlign: 'center' }}>Hành động</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((item) => (
                        <tr 
                          key={item.id} 
                          onClick={() => setSelectedItem(item)}
                          style={{ 
                            cursor: 'pointer', 
                            borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                            backgroundColor: selectedItem?.id === item.id ? 'rgba(79, 70, 229, 0.1)' : 'transparent',
                            transition: 'var(--transition)'
                          }}
                          className="history-row-hover"
                        >
                          <td style={{ padding: '0.9rem 1rem', fontWeight: 'bold' }}>
                            <span style={{ 
                              backgroundColor: 'var(--bg-primary)', 
                              border: '1px solid var(--border-color)', 
                              padding: '0.2rem 0.6rem', 
                              borderRadius: '4px',
                              fontFamily: 'monospace',
                              fontSize: '0.95rem'
                            }}>
                              {item.plate_text}
                            </span>
                          </td>
                          <td style={{ padding: '0.9rem 1rem' }}>
                            <span className="badge badge-conf" style={{ fontSize: '0.8rem' }}>
                              {(item.plate_confidence * 100).toFixed(2)}%
                            </span>
                          </td>
                          <td style={{ padding: '0.9rem 1rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            {new Date(item.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                            <br/>
                            {new Date(item.created_at).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}
                          </td>
                          <td style={{ padding: '0.9rem 1rem', textAlign: 'center' }}>
                            <button 
                              className="btn btn-danger btn-sm" 
                              onClick={(e) => handleDelete(item.id, e)}
                              style={{ padding: '0.3rem 0.5rem', minWidth: 'auto', borderRadius: '4px' }}
                              title="Xóa bản ghi"
                            >
                              <i className="fa-solid fa-trash-can" style={{ fontSize: '0.85rem' }}></i>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Right Panel: Selected Item Snapshot Preview */}
              <div style={{ width: '45%', display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: 'rgba(0, 0, 0, 0.15)', overflowY: 'auto' }}>
                {selectedItem ? (
                  <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.2rem', height: '100%' }}>
                    <div>
                      <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem', color: '#fff' }}>Chi tiết phát hiện</h3>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span>Biển số:</span>
                          <strong style={{ color: '#fff', fontSize: '1rem', fontFamily: 'monospace' }}>{selectedItem.plate_text}</strong>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span>Độ chính xác:</span>
                          <span className="badge badge-conf">{(selectedItem.plate_confidence * 100).toFixed(2)}%</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span>Thời gian lưu:</span>
                          <span style={{ color: 'var(--text-primary)' }}>{new Date(selectedItem.created_at).toLocaleString('vi-VN')}</span>
                        </div>
                      </div>
                    </div>

                    <div style={{ flex: 1, minHeight: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', overflow: 'hidden', backgroundColor: '#000' }}>
                      {selectedItem.image_path ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img 
                          src={selectedItem.image_path} 
                          alt="Ảnh chụp biển số xe" 
                          style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                        />
                      ) : (
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Không có ảnh chụp</div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    Chọn một bản ghi để xem ảnh chụp
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
