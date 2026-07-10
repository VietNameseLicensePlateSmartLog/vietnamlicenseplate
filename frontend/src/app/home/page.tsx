'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import ImageTab from '@/components/ImageTab';
import VideoTab from '@/components/VideoTab';
import RealtimeTab from '@/components/RealtimeTab';
import GeneralHistoryModal from '@/components/GeneralHistoryModal';
import AnimatedBackground from '@/components/AnimatedBackground';

import { API_BASE } from '@/lib/api';

function RequireLogin({ onLoginClick }: { onLoginClick: () => void }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '4rem 2rem', textAlign: 'center' }}>
      <i className="fa-solid fa-lock" style={{ fontSize: '3rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}></i>
      <h2 style={{ color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Vui lòng đăng nhập</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>Bạn cần đăng nhập để sử dụng tính năng này.</p>
      <button className="btn btn-primary" onClick={onLoginClick}>
        <i className="fa-solid fa-right-to-bracket"></i> Đăng nhập ngay
      </button>
    </div>
  );
}

export default function Home() {
  const router = useRouter();
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('realtime-tab');

  // Kiểm tra trạng thái đăng nhập từ localStorage khi component mount
  useEffect(() => {
    const savedLogin = localStorage.getItem('isLoggedIn');
    const savedUser = localStorage.getItem('currentUser');
    const savedRole = localStorage.getItem('userRole');
    if (savedLogin === 'true') {
      setIsLoggedIn(true);
      setCurrentUser(savedUser);
      setUserRole(savedRole);
      setActiveTab('image-tab'); // Nếu đã đăng nhập, mặc định vào tab nhận diện ảnh
    } else {
      setActiveTab('realtime-tab'); // Nếu chưa đăng nhập, mặc định vào tab camera realtime
    }
  }, []);

  const handleTabChange = useCallback((tab: string) => {
    setActiveTab(tab);
  }, []);

  const handleLogout = useCallback(async () => {
    const savedUser = localStorage.getItem('currentUser');
    if (savedUser) {
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: savedUser }),
        });
      } catch (err) {
        console.error('Lỗi khi gọi API đăng xuất:', err);
      }
    }
    setIsLoggedIn(false);
    setCurrentUser(null);
    setUserRole(null);
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('currentUser');
    localStorage.removeItem('userRole');
    localStorage.removeItem('userId');
    router.push('/login');
  }, [router]);

  return (
    <div className="app-container">
      {/* Animated Background */}
      <AnimatedBackground />

      <Navbar
        activeTab={activeTab}
        onTabChange={handleTabChange}
        isLoggedIn={isLoggedIn}
        onLoginClick={() => router.push('/login')}
        onLogoutClick={handleLogout}
        currentUser={currentUser}
        userRole={userRole}
        onHistoryClick={() => setIsHistoryModalOpen(true)}
      />

      <main className="main-content">
        {activeTab === 'image-tab' && (isLoggedIn ? <ImageTab /> : <RequireLogin onLoginClick={() => router.push('/login')} />)}
        {activeTab === 'video-tab' && (isLoggedIn ? <VideoTab /> : <RequireLogin onLoginClick={() => router.push('/login')} />)}
        {activeTab === 'realtime-tab' && <RealtimeTab />}
      </main>

      <footer className="app-footer">
        <p>Hệ thống Nhận diện Biển số xe Việt Nam (LPR) &copy; 2026. Công nghệ YOLOv8 Object Detection &amp; Classification.</p>
      </footer>

      <GeneralHistoryModal
        isOpen={isHistoryModalOpen}
        onClose={() => setIsHistoryModalOpen(false)}
      />
    </div>
  );
}
