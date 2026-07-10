'use client';

import { useState, useRef, useCallback } from 'react';
import { API_BASE } from '@/lib/api';

interface PlateResult {
  bbox: number[];
  text: string;
  conf: number;
}

export default function ImageTab() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewSrc, setPreviewSrc] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [annotatedImage, setAnnotatedImage] = useState<string>('');
  const [results, setResults] = useState<PlateResult[]>([]);
  const [hasResults, setHasResults] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelected = useCallback((file: File) => {
    if (!file.type.startsWith('image/')) {
      alert('Vui lòng chọn file hình ảnh hợp lệ!');
      return;
    }
    setSelectedFile(file);
    const reader = new FileReader();
    reader.onload = (e) => {
      setPreviewSrc(e.target?.result as string);
    };
    reader.readAsDataURL(file);
    // Reset results
    setHasResults(false);
    setAnnotatedImage('');
    setResults([]);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  }, [handleFileSelected]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  }, [handleFileSelected]);

  const handleRemoveImage = useCallback(() => {
    setSelectedFile(null);
    setPreviewSrc('');
    setHasResults(false);
    setAnnotatedImage('');
    setResults([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const handleProcess = useCallback(async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    setHasResults(false);

    const formData = new FormData();
    formData.append('file', selectedFile);

    // Lấy thông tin user_id từ localStorage nếu đã đăng nhập
    const userId = typeof window !== 'undefined' ? localStorage.getItem('userId') : null;
    const url = userId 
      ? `${API_BASE}/predict-image?user_id=${userId}`
      : `${API_BASE}/predict-image`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const data = await response.json();
      if (data.status === 'success') {
        setAnnotatedImage(data.annotated_image);
        setResults(data.results || []);
        setHasResults(true);
      } else {
        throw new Error(data.message || 'Lỗi nhận diện không xác định.');
      }
    } catch (error) {
      alert(`Lỗi khi gửi yêu cầu phân tích: ${(error as Error).message}`);
    } finally {
      setIsLoading(false);
    }
  }, [selectedFile]);

  return (
    <section className="tab-content active">
      <div className="grid-layout">
        {/* Left: Control & Upload Panel */}
        <div className="card upload-card">
          <div className="card-header">
            <h2>Tải ảnh lên hệ thống</h2>
            <p>Hỗ trợ các định dạng JPG, PNG, WEBP, BMP</p>
          </div>

          {!selectedFile ? (
            <div
              className={`dropzone ${isDragOver ? 'dragover' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                type="file"
                ref={fileInputRef}
                accept="image/*"
                className="file-input"
                onChange={handleInputChange}
                style={{ display: 'none' }}
              />
              <div className="dropzone-content">
                <div className="icon-circle">
                  <i className="fa-solid fa-cloud-arrow-up"></i>
                </div>
                <h3>Kéo &amp; Thả ảnh vào đây</h3>
                <p>hoặc <span>chọn file từ máy tính</span></p>
              </div>
            </div>
          ) : (
            <div className="preview-container">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {previewSrc && <img src={previewSrc} alt="Original Preview" />}
              <button className="btn btn-danger btn-sm" onClick={handleRemoveImage}>
                <i className="fa-solid fa-trash-can"></i> Xóa ảnh
              </button>
            </div>
          )}

          <button
            className="btn btn-primary btn-block mt-4"
            onClick={handleProcess}
            disabled={!selectedFile || isLoading}
          >
            <i className="fa-solid fa-microchip"></i> Bắt đầu nhận diện
          </button>
        </div>

        {/* Right: Results Panel */}
        <div className="card results-card">
          <div className="card-header">
            <h2>Kết quả nhận diện</h2>
            <p>Phân tích vị trí biển số xe và các ký tự</p>
          </div>

          {/* Empty State */}
          {!isLoading && !hasResults && (
            <div className="empty-state">
              <i className="fa-solid fa-receipt"></i>
              <h3>Chưa có kết quả phân tích</h3>
              <p>Hãy tải ảnh lên và nhấn nút nhận diện để bắt đầu phân tích biển số xe</p>
            </div>
          )}

          {/* Loading State */}
          {isLoading && (
            <div className="loader-container">
              <div className="spinner"></div>
              <p>Đang chạy phân tích AI qua 3 giai đoạn...</p>
            </div>
          )}

          {/* Content State */}
          {hasResults && (
            <div className="results-content">
              <div className="output-preview-container">
                <h3>Ảnh kết quả vẽ khung:</h3>
                <div className="annotated-wrapper">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  {annotatedImage && <img src={annotatedImage} alt="Annotated Output" />}
                </div>
              </div>

              <div className="output-data-container mt-4">
                <h3>Danh sách biển số phát hiện được:</h3>
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Tọa độ Bounding Box</th>
                        <th>Kết quả Biển số</th>
                        <th>Độ tin cậy</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.length > 0 ? (
                        results.map((plate, idx) => (
                          <tr key={idx}>
                            <td><strong>{idx + 1}</strong></td>
                            <td><span className="badge badge-code">[{plate.bbox.join(', ')}]</span></td>
                            <td><span className="badge badge-text">{plate.text}</span></td>
                            <td><span className="badge badge-conf">{(plate.conf * 100).toFixed(2)}%</span></td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                            Không phát hiện biển số xe nào trong ảnh.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
