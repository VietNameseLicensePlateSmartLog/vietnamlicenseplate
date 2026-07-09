'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { API_BASE, BACKEND_URL } from '@/lib/api';

interface TaskStatus {
  task_id: string;
  status: 'processing' | 'completed' | 'failed';
  progress: number;
  fps: number;
  current_frame: number;
  total_frames: number;
  error: string | null;
  eta_seconds?: number;
}

function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function formatETA(seconds: number): string {
  if (seconds <= 0) return 'Đang tính...';
  if (seconds < 60) return `~${seconds} giây`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins < 60) return `~${mins} phút ${secs}s`;
  const hrs = Math.floor(mins / 60);
  const remainMins = mins % 60;
  return `~${hrs}h ${remainMins} phút`;
}

export default function VideoTab() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Dọn dẹp interval khi component unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const handleFileSelected = useCallback((file: File) => {
    if (!file.type.startsWith('video/') && 
        !file.name.endsWith('.mp4') && 
        !file.name.endsWith('.avi') && 
        !file.name.endsWith('.mov') && 
        !file.name.endsWith('.mkv')) {
      alert('Vui lòng chọn file video hợp lệ!');
      return;
    }
    setSelectedFile(file);
    // Reset task state
    setTaskId(null);
    setTaskStatus(null);
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

  const handleRemoveVideo = useCallback(() => {
    setSelectedFile(null);
    setTaskId(null);
    setTaskStatus(null);
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const startPolling = useCallback((id: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/tasks/${id}`);
        if (!response.ok) {
          throw new Error(`Lỗi HTTP ${response.status}`);
        }
        const task: TaskStatus = await response.json();
        setTaskStatus(task);

        if (task.status === 'completed' || task.status === 'failed') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        }
      } catch (error) {
        console.error('Lỗi khi lấy tiến trình:', error);
      }
    }, 1000);
  }, []);

  const handleProcess = useCallback(async () => {
    if (!selectedFile) return;

    setIsSubmitting(true);
    setTaskStatus(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    // Lấy thông tin user_id từ localStorage nếu đã đăng nhập
    const userId = typeof window !== 'undefined' ? localStorage.getItem('userId') : null;
    const url = userId 
      ? `${BACKEND_URL}/predict-video?user_id=${userId}`
      : `${BACKEND_URL}/predict-video`;

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
        const id = data.task_id;
        setTaskId(id);
        setTaskStatus({
          task_id: id,
          status: 'processing',
          progress: 0,
          fps: 0,
          current_frame: 0,
          total_frames: 0,
          error: null,
        });
        startPolling(id);
      } else {
        throw new Error(data.message || 'Không khởi chạy được tác vụ.');
      }
    } catch (error) {
      alert(`Lỗi khi tạo tác vụ: ${(error as Error).message}`);
    } finally {
      setIsSubmitting(false);
    }
  }, [selectedFile, startPolling]);

  const isProcessing = taskStatus?.status === 'processing';
  const isCompleted = taskStatus?.status === 'completed';
  const isFailed = taskStatus?.status === 'failed';

  return (
    <section className="tab-content active">
      <div className="grid-layout">
        {/* Left: Control & Upload Panel */}
        <div className="card upload-card">
          <div className="card-header">
            <h2>Tải video lên hệ thống</h2>
            <p>Hỗ trợ các định dạng MP4, AVI, MOV, MKV</p>
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
                accept="video/*"
                className="file-input"
                onChange={handleInputChange}
                style={{ display: 'none' }}
              />
              <div className="dropzone-content">
                <div className="icon-circle">
                  <i className="fa-solid fa-video"></i>
                </div>
                <h3>Kéo &amp; Thả video vào đây</h3>
                <p>hoặc <span>chọn file từ máy tính</span></p>
              </div>
            </div>
          ) : (
            <div className="preview-container">
              <div className="video-info-box">
                <i className="fa-solid fa-file-video text-primary"></i>
                <div className="video-info-text">
                  <span className="filename">{selectedFile.name}</span>
                  <span className="filesize">{formatBytes(selectedFile.size)}</span>
                </div>
              </div>
              <button className="btn btn-danger btn-sm mt-3" onClick={handleRemoveVideo} disabled={isProcessing}>
                <i className="fa-solid fa-trash-can"></i> Xóa video
              </button>
            </div>
          )}

          <button
            className="btn btn-primary btn-block mt-4"
            onClick={handleProcess}
            disabled={!selectedFile || isSubmitting || isProcessing}
          >
            <i className="fa-solid fa-circle-play"></i> Bắt đầu xử lý video
          </button>
        </div>

        {/* Right: Progress Dashboard */}
        <div className="card results-card">
          <div className="card-header">
            <h2>Tiến trình xử lý video</h2>
            <p>Xử lý từng khung hình độc lập bằng luồng xử lý ngầm (Background Task)</p>
          </div>

          {/* Empty State */}
          {!taskStatus && (
            <div className="empty-state">
              <i className="fa-solid fa-bars-progress"></i>
              <h3>Chưa có tác vụ nào đang chạy</h3>
              <p>Tải video lên và nhấn nút khởi chạy để tạo tác vụ xử lý nền</p>
            </div>
          )}

          {/* Active Task State */}
          {taskStatus && (
            <div className="video-task-content">
              <div className="task-status-banner">
                <div className="status-indicator">
                  <span className={`status-pulse ${
                    isCompleted ? 'pulse-completed' : isFailed ? 'pulse-failed' : 'pulse-processing'
                  }`}></span>
                  <span className="status-label">
                    {isCompleted ? 'Đã hoàn thành' : isFailed ? 'Thất bại' : 'Đang xử lý'}
                  </span>
                </div>
                <span className="task-id-text">
                  Task ID: {taskId ? `${taskId.substring(0, 8)}...` : 'N/A'}
                </span>
              </div>

              <div className="progress-section mt-4">
                <div className="progress-details">
                  <span>Tiến độ xử lý</span>
                  <span className="progress-percentage">{taskStatus.progress}%</span>
                </div>
                <div className="progress-bar-bg">
                  <div
                    className="progress-bar-fill"
                    style={{ width: `${taskStatus.progress}%` }}
                  ></div>
                </div>
              </div>

              <div className="stats-grid mt-4">
                <div className="stat-box">
                  <span className="stat-title">Tốc độ xử lý</span>
                  <span className="stat-value">{taskStatus.fps.toFixed(1)} khung hình/giây</span>
                </div>
                <div className="stat-box">
                  <span className="stat-title">Khung hình hiện tại</span>
                  <span className="stat-value">{taskStatus.current_frame.toLocaleString()} / {taskStatus.total_frames.toLocaleString()}</span>
                </div>
              </div>

              {/* ETA = (frames còn lại) / fps, cả backend và frontend đều dùng raw frames */}
              {isProcessing && taskStatus.fps > 0 && taskStatus.current_frame > 0 && taskStatus.current_frame < taskStatus.total_frames && (
                <div className="mt-3" style={{ textAlign: 'center', opacity: 0.8, fontSize: '0.9rem' }}>
                  <span>⏱️ Ước tính còn lại: {formatETA(Math.ceil((taskStatus.total_frames - taskStatus.current_frame) / taskStatus.fps))}</span>
                </div>
              )}

              <div className="action-section mt-5">
                {/* Processing spinner */}
                {isProcessing && (
                  <div className="processing-spinner-info">
                    <div className="small-spinner"></div>
                    <span>Đang phân tích và render video, vui lòng không đóng trang...</span>
                  </div>
                )}

                {/* Done actions */}
                {isCompleted && taskId && (
                  <div className="download-container">
                    <div className="success-message">
                      <i className="fa-solid fa-circle-check"></i>
                      <span>Video đã được xử lý xong thành công!</span>
                    </div>
                    <a
                      href={`${BACKEND_URL}/tasks/${taskId}/download`}
                      className="btn btn-success btn-lg btn-block mt-3"
                    >
                      <i className="fa-solid fa-circle-down"></i> Tải Video Kết Quả (.mp4)
                    </a>
                  </div>
                )}

                {/* Error actions */}
                {isFailed && (
                  <div className="error-container">
                    <div className="error-message">
                      <i className="fa-solid fa-circle-exclamation"></i>
                      <span>{taskStatus.error || 'Đã xảy ra lỗi khi xử lý video.'}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
