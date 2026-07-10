'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function TopBar() {
  const router = useRouter();
  const [username, setUsername] = useState('Admin');

  useEffect(() => {
    const savedUser = localStorage.getItem('currentUser');
    if (savedUser) {
      setUsername(savedUser);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('currentUser');
    localStorage.removeItem('userRole');
    router.push('/home');
  };

  return (
    <header id="top-bar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
        <button
          onClick={() => router.push('/home')}
          style={{
            backgroundColor: 'rgba(59, 130, 246, 0.2)',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            color: '#93c5fd',
            padding: '6px 12px',
            borderRadius: '6px',
            cursor: 'pointer',
            transition: 'all 0.2s',
            fontSize: '0.9rem'
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.4)';
            e.currentTarget.style.transform = 'scale(1.05)';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.2)';
            e.currentTarget.style.transform = 'scale(1)';
          }}
        >
          <i className="fa-solid fa-house" style={{ marginRight: '5px' }}></i>
          Trang chủ
        </button>
        <span style={{ fontSize: '0.95rem', color: 'rgba(255, 255, 255, 0.7)' }}>
          Xin chào, <strong style={{ color: '#fff' }}>{username}</strong>
        </span>
        <button
          onClick={handleLogout}
          style={{
            backgroundColor: 'rgba(239, 68, 68, 0.2)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            color: '#fca5a5',
            padding: '6px 12px',
            borderRadius: '6px',
            cursor: 'pointer',
            transition: 'all 0.2s',
            fontSize: '0.9rem'
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.4)';
            e.currentTarget.style.transform = 'scale(1.05)';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
            e.currentTarget.style.transform = 'scale(1)';
          }}
        >
          <i className="fa-solid fa-right-from-bracket" style={{ marginRight: '5px' }}></i>
          Đăng xuất
        </button>
      </div>
    </header>
  );
}
