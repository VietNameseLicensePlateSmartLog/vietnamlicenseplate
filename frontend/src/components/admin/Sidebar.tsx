'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import '@/styles/admin.css';

const menuItems = [
  { name: 'Dashboard', href: '/admin/dashboard' },
  { name: 'Xác minh', href: '/admin/verification' },
  { name: 'Quản lý người dùng', href: '/admin/users' },
  { name: 'Quản lý Camera', href: '/admin/cameras' },
  { name: 'Tỷ lệ dự đoán', href: '/admin/prediction-ratio' },
  { name: 'Thống kê biến số', href: '/admin/variable-stats' },
  { name: 'Nhật ký hoạt động', href: '/admin/activity-log' },
  { name: 'Tra cứu dữ liệu', href: '/admin/search' },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside id="sidebar" className="sidebar">
      <h2 className="sidebar-title">Admin</h2>
      <nav>
        {menuItems.map(item => (
          <Link key={item.href} href={item.href} className={`sidebar-item ${pathname === item.href ? 'active' : ''}`}>
            {item.name}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
