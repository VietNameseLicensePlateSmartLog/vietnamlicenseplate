'use client';

interface SnapshotModalProps {
  isOpen: boolean;
  onClose: () => void;
  plateText: string;
  timeRange: string;
  confidence: number;
  snapshotSrc: string;
}

export default function SnapshotModal({
  isOpen,
  onClose,
  plateText,
  timeRange,
  confidence,
  snapshotSrc,
}: SnapshotModalProps) {
  if (!isOpen) return null;

  return (
    <div className="modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-content">
        <div className="modal-header">
          <h2>Chi tiết xe phát hiện</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="modal-info">
            <div>
              <span className="modal-label">Biển số nhận diện:</span>
              <span className="modal-value modal-plate-text">{plateText}</span>
            </div>
            <div>
              <span className="modal-label">Mốc thời gian (Thời lượng):</span>
              <span className="modal-value">{timeRange}</span>
            </div>
            <div>
              <span className="modal-label">Độ tin cậy lớn nhất:</span>
              <span className="badge badge-conf">{(confidence * 100).toFixed(2)}%</span>
            </div>
          </div>
          <div className="modal-image-container">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={snapshotSrc} alt="Ảnh chụp biển số xe" />
          </div>
        </div>
      </div>
    </div>
  );
}
