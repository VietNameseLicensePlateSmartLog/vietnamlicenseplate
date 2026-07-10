'use client';

import Link from 'next/link';

interface NavbarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  isLoggedIn: boolean;
  onLoginClick: () => void;
  onLogoutClick: () => void;
  currentUser?: string | null;
  userRole?: string | null;
  onHistoryClick: () => void;
}

export default function Navbar({
  activeTab,
  onTabChange,
  isLoggedIn,
  onLoginClick,
  onLogoutClick,
  currentUser,
  userRole,
  onHistoryClick,
}: NavbarProps) {
  const tabs = [
    { id: 'image-tab', icon: 'fa-regular fa-image', label: 'Nhận diện Ảnh', requireAuth: true },
    { id: 'video-tab', icon: 'fa-regular fa-file-video', label: 'Nhận diện Video', requireAuth: true },
    { id: 'realtime-tab', icon: 'fa-solid fa-camera', label: 'Camera Realtime', requireAuth: false },
  ];

  return (
    <header className="navbar">
      <div className="brand">
        <div className="brand-icon">
          <i className="fa-solid fa-car-rear"></i>
        </div>
        <div className="brand-text">
          <h1>Vietnam LPR</h1>
          <span>YOLO 3-Stage Pipeline</span>
        </div>
      </div>

      <nav className="nav-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => {
              if (tab.requireAuth && !isLoggedIn) {
                onTabChange(tab.id);   // Chuyển tab để hiện RequireLogin
                onLoginClick();        // Đồng thời mở modal đăng nhập
              } else {
                onTabChange(tab.id);
              }
            }}
          >
            <i className={tab.icon}></i>
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>

      <div className="navbar-actions" style={{ display: 'flex', alignItems: 'center', gap: '1.2rem' }}>
        {isLoggedIn && (
          <button 
            className="btn btn-secondary btn-sm" 
            onClick={onHistoryClick}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.4rem', 
              backgroundColor: 'rgba(255, 255, 255, 0.05)', 
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              borderRadius: 'var(--radius-md)'
            }}
          >
            <i className="fa-solid fa-clock-rotate-left"></i>
            <span>Lịch sử tổng quát</span>
          </button>
        )}
        {isLoggedIn && userRole === 'admin' && (
          <Link 
            href="/admin"
            className="btn btn-secondary btn-sm" 
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.4rem', 
              backgroundColor: 'rgba(79, 70, 229, 0.2)', 
              border: '1px solid rgba(79, 70, 229, 0.4)',
              color: '#a5b4fc',
              borderRadius: 'var(--radius-md)',
              textDecoration: 'none'
            }}
          >
            <i className="fa-solid fa-user-shield"></i>
            <span>Trang Admin</span>
          </Link>
        )}

        {isLoggedIn ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
            <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={currentUser || 'Admin'}>
              <i className="fa-regular fa-circle-user" style={{ marginRight: '0.4rem', color: 'var(--primary)' }}></i>
              {currentUser || 'Admin'}
            </span>
            <button className="btn btn-danger btn-sm" onClick={onLogoutClick}>
              <i className="fa-solid fa-right-from-bracket"></i> Đăng xuất
            </button>
          </div>
        ) : (
          <Link href="/login" className="btn btn-primary btn-sm" style={{ textDecoration: 'none' }}>
            <i className="fa-solid fa-right-to-bracket"></i> Đăng nhập
          </Link>
        )}
      </div>
    </header>
  );
}
