import React from 'react';
import Sidebar from '@/components/admin/Sidebar';
import TopBar from '@/components/admin/TopBar';
import AnimatedBackground from '@/components/AnimatedBackground';
import '@/styles/admin.css';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div id="admin-app">
      <AnimatedBackground />
      <Sidebar />
      <div className="admin-main">
        <TopBar />
        <main className="admin-content">{children}</main>
      </div>
    </div>
  );
}
