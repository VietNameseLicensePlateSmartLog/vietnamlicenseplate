'use client';

import { useState, useEffect } from 'react';
import { API_BASE } from '@/lib/api';

interface DailyChartItem { date: string; count: number; }
interface SourceChartItem { source: string; count: number; }
interface TopPlateItem { plate: string; count: number; }
interface ConfDistItem { label: string; count: number; }

interface StatsData {
  total_users: number;
  total_detections: number;
  total_verified: number;
  unverified: number;
  correct: number;
  incorrect: number;
  accuracy: number;
  avg_confidence: number;
  daily_chart: DailyChartItem[];
  source_chart: SourceChartItem[];
  top_plates: TopPlateItem[];
  conf_distribution: ConfDistItem[];
}

// ===== SVG Donut Chart Component =====
function DonutChart({ segments, size = 160, thickness = 24 }: { segments: { label: string; value: number; color: string }[]; size?: number; thickness?: number }) {
  const total = segments.reduce((s, seg) => s + seg.value, 0);
  if (total === 0) return <div style={{ width: size, height: size, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,0.3)', fontSize: '0.85rem' }}>Không có dữ liệu</div>;

  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  let accumulated = 0;

  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={thickness} />
      {segments.map((seg, i) => {
        if (seg.value === 0) return null;
        const pct = seg.value / total;
        const dashLen = circumference * pct;
        const dashOff = circumference * accumulated;
        accumulated += pct;
        return (
          <circle
            key={i}
            cx={size/2} cy={size/2} r={radius}
            fill="none"
            stroke={seg.color}
            strokeWidth={thickness}
            strokeDasharray={`${dashLen} ${circumference - dashLen}`}
            strokeDashoffset={-dashOff}
            strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 0.8s ease' }}
          />
        );
      })}
    </svg>
  );
}

// ===== Horizontal Bar Component =====
function HBar({ label, value, maxValue, color }: { label: string; value: number; maxValue: number; color: string }) {
  const pct = maxValue > 0 ? (value / maxValue) * 100 : 0;
  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px', fontSize: '0.85rem' }}>
        <span style={{ color: 'rgba(255,255,255,0.7)' }}>{label}</span>
        <span style={{ fontWeight: 600, color }}>{value}</span>
      </div>
      <div style={{ height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' }}>
        <div style={{ height: '100%', background: color, width: `${pct}%`, borderRadius: '4px', transition: 'width 0.8s ease' }} />
      </div>
    </div>
  );
}


export default function Dashboard() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchStats = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE}/admin/stats`);
      if (!res.ok) throw new Error('Không thể tải số liệu thống kê.');
      const data = await res.json();
      setStats(data);
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối API.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchStats(); }, []);

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

  const maxDaily = stats.daily_chart.length > 0 ? Math.max(...stats.daily_chart.map(d => d.count)) : 10;
  const maxPlate = stats.top_plates.length > 0 ? Math.max(...stats.top_plates.map(p => p.count)) : 1;
  const maxConf = stats.conf_distribution.length > 0 ? Math.max(...stats.conf_distribution.map(c => c.count)) : 1;

  const sourceSegments = stats.source_chart.map(s => ({
    label: s.source === 'image' ? 'Ảnh' : s.source === 'video' ? 'Video' : 'Camera',
    value: s.count,
    color: s.source === 'image' ? '#60a5fa' : s.source === 'video' ? '#34d399' : '#fbbf24',
  }));

  const verifySegments = [
    { label: 'Đúng', value: stats.correct, color: '#10b981' },
    { label: 'Sai', value: stats.incorrect, color: '#ef4444' },
  ];

  return (
    <>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 600 }}>Tổng quan hệ thống</h1>
          <p style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.9rem' }}>Bảng số liệu thống kê thời gian thực</p>
        </div>
        <button onClick={fetchStats} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <i className="fa-solid fa-rotate"></i> Làm mới
        </button>
      </div>

      {/* ===== 6 STAT CARDS ===== */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '16px', marginBottom: '20px' }}>
        {[
          { icon: 'fa-users', label: 'Người dùng', value: stats.total_users, bg: 'rgba(79, 70, 229, 0.2)', color: '#a5b4fc' },
          { icon: 'fa-car-rear', label: 'Biển số', value: stats.total_detections, bg: 'rgba(16, 185, 129, 0.2)', color: '#34d399' },
          { icon: 'fa-square-check', label: 'Đã xác minh', value: stats.total_verified, bg: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24' },
          { icon: 'fa-percent', label: 'Độ chính xác', value: `${stats.accuracy}%`, bg: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa' },
          { icon: 'fa-chart-line', label: 'Confidence TB', value: `${stats.avg_confidence}%`, bg: 'rgba(168, 85, 247, 0.2)', color: '#c084fc' },
          { icon: 'fa-circle-question', label: 'Chưa xác minh', value: stats.unverified, bg: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5' },
        ].map((card, i) => (
          <div key={i} className="card" style={{ display: 'flex', alignItems: 'center', gap: '14px', padding: '18px' }}>
            <div style={{ padding: '12px', borderRadius: '10px', background: card.bg, color: card.color, fontSize: '1.3rem', display: 'flex', justifyContent: 'center', alignItems: 'center', flexShrink: 0 }}>
              <i className={`fa-solid ${card.icon}`}></i>
            </div>
            <div>
              <h4 style={{ color: 'rgba(255,255,255,0.5)', fontWeight: 400, fontSize: '0.78rem', marginBottom: '2px' }}>{card.label}</h4>
              <span style={{ fontSize: '1.5rem', fontWeight: 700 }}>{card.value}</span>
            </div>
          </div>
        ))}
      </div>

      {/* ===== ROW 2: Daily Chart + Source Donut ===== */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px', marginBottom: '20px' }}>
        {/* Daily Bar Chart */}
        <div className="card">
          <h3 style={{ fontSize: '1rem', marginBottom: '20px', fontWeight: 600 }}>
            <i className="fa-solid fa-chart-column" style={{ color: 'var(--primary)', marginRight: '8px' }}></i>
            Tần suất nhận diện (7 ngày)
          </h3>
          {stats.daily_chart.length === 0 ? (
            <div style={{ height: '200px', display: 'flex', justifyContent: 'center', alignItems: 'center', color: 'rgba(255,255,255,0.4)' }}>
              Chưa có dữ liệu
            </div>
          ) : (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', height: '200px', padding: '0 5px' }}>
              {stats.daily_chart.map((item, idx) => {
                const h = maxDaily > 0 ? (item.count / maxDaily) * 75 + 10 : 10;
                const displayDate = item.date.substring(5); // MM-DD
                return (
                  <div key={idx} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1, height: '100%', justifyContent: 'flex-end', gap: '8px' }}>
                    <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'rgba(255,255,255,0.8)' }}>{item.count}</span>
                    <div style={{ width: '32px', height: `${h}%`, background: 'linear-gradient(180deg, #818cf8, #4f46e5)', borderRadius: '4px 4px 0 0', transition: 'height 0.6s ease' }} />
                    <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.4)' }}>{displayDate}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Source Distribution Donut */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <h3 style={{ fontSize: '1rem', marginBottom: '20px', fontWeight: 600, alignSelf: 'flex-start' }}>
            <i className="fa-solid fa-chart-pie" style={{ color: '#34d399', marginRight: '8px' }}></i>
            Phân bổ theo nguồn
          </h3>
          <div style={{ position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <DonutChart segments={sourceSegments} size={150} thickness={22} />
            <div style={{ position: 'absolute', textAlign: 'center' }}>
              <span style={{ fontSize: '1.4rem', fontWeight: 700 }}>{stats.total_detections}</span>
              <br/>
              <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.5)' }}>tổng</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '16px', marginTop: '16px', flexWrap: 'wrap', justifyContent: 'center' }}>
            {sourceSegments.map((seg, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: seg.color }} />
                <span style={{ color: 'rgba(255,255,255,0.6)' }}>{seg.label}</span>
                <span style={{ fontWeight: 600 }}>{seg.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ===== ROW 3: Verification Donut + Top Plates + Confidence ===== */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
        {/* Verification Donut */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <h3 style={{ fontSize: '1rem', marginBottom: '20px', fontWeight: 600, alignSelf: 'flex-start' }}>
            <i className="fa-solid fa-circle-check" style={{ color: '#fbbf24', marginRight: '8px' }}></i>
            Tỷ lệ xác minh
          </h3>
          <div style={{ position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <DonutChart segments={verifySegments} size={140} thickness={20} />
            <div style={{ position: 'absolute', textAlign: 'center' }}>
              <span style={{ fontSize: '1.6rem', fontWeight: 700, color: stats.accuracy >= 80 ? '#34d399' : '#fbbf24' }}>{stats.accuracy}%</span>
              <br/>
              <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.5)' }}>chính xác</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '20px', marginTop: '14px' }}>
            <div style={{ textAlign: 'center' }}>
              <span style={{ display: 'block', fontSize: '1.1rem', fontWeight: 700, color: '#34d399' }}>{stats.correct}</span>
              <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.5)' }}>Đúng</span>
            </div>
            <div style={{ textAlign: 'center' }}>
              <span style={{ display: 'block', fontSize: '1.1rem', fontWeight: 700, color: '#fca5a5' }}>{stats.incorrect}</span>
              <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.5)' }}>Sai</span>
            </div>
            <div style={{ textAlign: 'center' }}>
              <span style={{ display: 'block', fontSize: '1.1rem', fontWeight: 700, color: 'rgba(255,255,255,0.6)' }}>{stats.unverified}</span>
              <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.5)' }}>Chưa XD</span>
            </div>
          </div>
        </div>

        {/* Top Plates */}
        <div className="card">
          <h3 style={{ fontSize: '1rem', marginBottom: '20px', fontWeight: 600 }}>
            <i className="fa-solid fa-trophy" style={{ color: '#fbbf24', marginRight: '8px' }}></i>
            Top biển số nhận diện
          </h3>
          {stats.top_plates.length === 0 ? (
            <div style={{ height: '120px', display: 'flex', justifyContent: 'center', alignItems: 'center', color: 'rgba(255,255,255,0.4)', fontSize: '0.9rem' }}>
              Chưa có dữ liệu
            </div>
          ) : (
            <div>
              {stats.top_plates.map((item, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                  <span style={{ width: '20px', fontSize: '0.85rem', fontWeight: 700, color: i === 0 ? '#fbbf24' : i === 1 ? '#94a3b8' : i === 2 ? '#cd7f32' : 'rgba(255,255,255,0.3)', textAlign: 'center' }}>
                    {i + 1}
                  </span>
                  <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '0.9rem', minWidth: '90px' }}>{item.plate}</span>
                  <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', background: 'linear-gradient(90deg, #4f46e5, #818cf8)', width: `${(item.count / maxPlate) * 100}%`, borderRadius: '3px' }} />
                  </div>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'rgba(255,255,255,0.6)', minWidth: '30px', textAlign: 'right' }}>{item.count}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Confidence Distribution */}
        <div className="card">
          <h3 style={{ fontSize: '1rem', marginBottom: '20px', fontWeight: 600 }}>
            <i className="fa-solid fa-gauge-high" style={{ color: '#c084fc', marginRight: '8px' }}></i>
            Phân bố Confidence
          </h3>
          {stats.conf_distribution.every(c => c.count === 0) ? (
            <div style={{ height: '120px', display: 'flex', justifyContent: 'center', alignItems: 'center', color: 'rgba(255,255,255,0.4)', fontSize: '0.9rem' }}>
              Chưa có dữ liệu
            </div>
          ) : (
            <div>
              {stats.conf_distribution.map((item, i) => {
                const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'];
                return (
                  <HBar key={i} label={item.label} value={item.count} maxValue={maxConf} color={colors[i]} />
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
