'use client';

import { useState, useEffect } from 'react';
import { API_BASE } from '@/lib/api';

interface UserData {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  role: string;
  is_verified: number;
  is_active: boolean;
  failed_attempts: number;
  created_at: string | null;
}

export default function UsersManagement() {
  const [users, setUsers] = useState<UserData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [toggleLoading, setToggleLoading] = useState<{ [key: number]: boolean }>({});

  // Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({ username: '', email: '', password: '', role: 'user' });
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState('');

  // Delete confirm
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Role change loading
  const [roleLoading, setRoleLoading] = useState<{ [key: number]: boolean }>({});

  const fetchUsers = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE}/admin/users`);
      if (!res.ok) throw new Error('Không thể tải danh sách tài khoản.');
      const data = await res.json();
      setUsers(data);
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối API.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  // ===== Toggle Active =====
  const handleToggleActive = async (userId: number) => {
    setToggleLoading(prev => ({ ...prev, [userId]: true }));
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/toggle-active`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi khi thay đổi trạng thái.');
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: data.is_active } : u));
    } catch (err: any) {
      alert(err.message);
    } finally {
      setToggleLoading(prev => ({ ...prev, [userId]: false }));
    }
  };

  // ===== Create User =====
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError('');
    setCreateLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(createForm),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi khi tạo tài khoản.');
      setShowCreateModal(false);
      setCreateForm({ username: '', email: '', password: '', role: 'user' });
      fetchUsers();
    } catch (err: any) {
      setCreateError(err.message);
    } finally {
      setCreateLoading(false);
    }
  };

  // ===== Change Role =====
  const handleChangeRole = async (userId: number, newRole: string) => {
    setRoleLoading(prev => ({ ...prev, [userId]: true }));
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/role`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi khi đổi role.');
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: data.role } : u));
    } catch (err: any) {
      alert(err.message);
      fetchUsers(); // reload to sync
    } finally {
      setRoleLoading(prev => ({ ...prev, [userId]: false }));
    }
  };

  // ===== Delete User =====
  const handleDeleteUser = async (userId: number) => {
    setDeleteLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi khi xóa tài khoản.');
      setDeleteConfirmId(null);
      fetchUsers();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flex: 1, justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 600 }}>Quản lý tài khoản</h1>
          <p style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.9rem' }}>Quản lý trạng thái hoạt động và phân quyền người dùng trong hệ thống</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={() => setShowCreateModal(true)} style={{ display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: '#10b981', border: 'none' }}>
            <i className="fa-solid fa-plus"></i> Thêm tài khoản
          </button>
          <button onClick={fetchUsers} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <i className="fa-solid fa-rotate"></i> Tải lại
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ padding: '20px', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#fca5a5', marginBottom: '20px' }}>
          <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '8px' }}></i> {error}
        </div>
      )}

      {/* ===== TABLE ===== */}
      <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
        <div className="table-scroll-container">
          <table style={{ minWidth: '900px' }}>
            <thead>
              <tr>
                <th style={{ width: '70px' }}>ID</th>
                <th>Tài khoản</th>
                <th>Email</th>
                <th style={{ width: '130px' }}>Vai trò</th>
                <th style={{ width: '120px' }}>Xác thực</th>
                <th style={{ width: '100px', textAlign: 'center' }}>Sai MK</th>
                <th style={{ width: '130px' }}>Trạng thái</th>
                <th style={{ width: '200px', textAlign: 'center' }}>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '30px', color: 'rgba(255,255,255,0.4)' }}>
                    Không tìm thấy tài khoản nào
                  </td>
                </tr>
              ) : (
                users.map(user => {
                  const isChanging = toggleLoading[user.id];
                  const isRoleChanging = roleLoading[user.id];
                  const isProtectedAdmin = user.username === 'abc1';

                  return (
                    <tr key={user.id}>
                      <td style={{ fontWeight: 600, color: 'rgba(255,255,255,0.5)' }}>#{user.id}</td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontWeight: 600 }}>{user.username}</span>
                          {user.full_name && <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.5)' }}>{user.full_name}</span>}
                        </div>
                      </td>
                      <td style={{ fontSize: '0.9rem' }}>{user.email}</td>
                      <td>
                        {isProtectedAdmin ? (
                          <span style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '0.8rem', background: 'rgba(79, 70, 229, 0.2)', border: '1px solid rgba(79, 70, 229, 0.4)', color: '#a5b4fc', fontWeight: 600 }}>
                            admin
                          </span>
                        ) : (
                          <select
                            value={user.role}
                            onChange={(e) => handleChangeRole(user.id, e.target.value)}
                            disabled={isRoleChanging}
                            style={{
                              padding: '4px 8px',
                              borderRadius: '4px',
                              fontSize: '0.85rem',
                              background: user.role === 'admin' ? 'rgba(79, 70, 229, 0.15)' : 'rgba(255,255,255,0.05)',
                              border: '1px solid rgba(255,255,255,0.15)',
                              color: '#e2e8f0',
                              cursor: 'pointer',
                              fontWeight: 500,
                            }}
                          >
                            <option value="user" style={{ background: '#1c2230' }}>user</option>
                            <option value="admin" style={{ background: '#1c2230' }}>admin</option>
                          </select>
                        )}
                      </td>
                      <td>
                        <span style={{ color: user.is_verified === 1 ? '#10b981' : '#f59e0b', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <i className={user.is_verified === 1 ? "fa-solid fa-circle-check" : "fa-solid fa-circle-minus"}></i>
                          {user.is_verified === 1 ? 'Đã xác thực' : 'Chờ xác thực'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span style={{ color: user.failed_attempts > 0 ? '#ef4444' : 'rgba(255,255,255,0.4)', fontWeight: user.failed_attempts > 0 ? 600 : 400 }}>
                          {user.failed_attempts}
                        </span>
                      </td>
                      <td>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: '6px',
                          padding: '4px 10px', borderRadius: '20px', fontSize: '0.8rem',
                          background: user.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                          color: user.is_active ? '#34d399' : '#fca5a5', fontWeight: 600
                        }}>
                          <i className="fa-solid fa-circle" style={{ fontSize: '0.5rem' }}></i>
                          {user.is_active ? 'Đang hoạt động' : 'Bị chặn'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        {isProtectedAdmin ? (
                          <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.3)', fontStyle: 'italic' }}>Bảo vệ</span>
                        ) : (
                          <div style={{ display: 'flex', gap: '6px', justifyContent: 'center' }}>
                            <button
                              onClick={() => handleToggleActive(user.id)}
                              disabled={isChanging}
                              style={{
                                backgroundColor: user.is_active ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                                border: user.is_active ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(16, 185, 129, 0.4)',
                                color: user.is_active ? '#fca5a5' : '#a7f3d0',
                                padding: '5px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem',
                                display: 'inline-flex', alignItems: 'center', gap: '4px'
                              }}
                            >
                              {isChanging ? <i className="fa-solid fa-spinner fa-spin"></i> : user.is_active ? <i className="fa-solid fa-ban"></i> : <i className="fa-solid fa-unlock"></i>}
                            </button>
                            <button
                              onClick={() => setDeleteConfirmId(user.id)}
                              style={{
                                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                                border: '1px solid rgba(239, 68, 68, 0.3)',
                                color: '#fca5a5', padding: '5px 10px', borderRadius: '6px',
                                cursor: 'pointer', fontSize: '0.8rem',
                                display: 'inline-flex', alignItems: 'center', gap: '4px'
                              }}
                            >
                              <i className="fa-solid fa-trash-can"></i>
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ===== MODAL: TẠO TÀI KHOẢN ===== */}
      {showCreateModal && (
        <div className="modal" onClick={(e) => { if (e.target === e.currentTarget) setShowCreateModal(false); }}>
          <div className="modal-content" style={{ maxWidth: '420px' }}>
            <div className="modal-header">
              <h2>Thêm tài khoản mới</h2>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>&times;</button>
            </div>
            <div className="modal-body">
              <form onSubmit={handleCreateUser} className="form-group" style={{ gap: '1.2rem' }}>
                <div className="form-group">
                  <label className="form-label"><i className="fa-regular fa-user"></i> Tên tài khoản:</label>
                  <input
                    type="text" className="form-input" placeholder="Ít nhất 3 ký tự"
                    value={createForm.username}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, username: e.target.value }))}
                    required minLength={3} disabled={createLoading}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label"><i className="fa-regular fa-envelope"></i> Email:</label>
                  <input
                    type="email" className="form-input" placeholder="email@example.com"
                    value={createForm.email}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, email: e.target.value }))}
                    required disabled={createLoading}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label"><i className="fa-solid fa-lock"></i> Mật khẩu:</label>
                  <input
                    type="password" className="form-input" placeholder="Ít nhất 6 ký tự"
                    value={createForm.password}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, password: e.target.value }))}
                    required minLength={6} disabled={createLoading}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label"><i className="fa-solid fa-shield-halved"></i> Vai trò:</label>
                  <select
                    className="form-select"
                    value={createForm.role}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, role: e.target.value }))}
                    disabled={createLoading}
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>

                {createError && (
                  <div style={{ padding: '0.8rem', fontSize: '0.85rem', color: '#fca5a5', backgroundColor: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                    <i className="fa-solid fa-triangle-exclamation" style={{ marginRight: '6px' }}></i>{createError}
                  </div>
                )}

                <button type="submit" className="btn btn-primary btn-block mt-2" disabled={createLoading}>
                  {createLoading ? <><div className="small-spinner" style={{ marginRight: '0.5rem' }}></div>Đang tạo...</> : <><i className="fa-solid fa-plus" style={{ marginRight: '6px' }}></i>Tạo tài khoản</>}
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* ===== MODAL: XÁC NHẬN XÓA ===== */}
      {deleteConfirmId !== null && (
        <div className="modal" onClick={(e) => { if (e.target === e.currentTarget) setDeleteConfirmId(null); }}>
          <div className="modal-content" style={{ maxWidth: '380px', textAlign: 'center' }}>
            <div className="modal-header" style={{ justifyContent: 'center' }}>
              <h2 style={{ color: '#fca5a5' }}><i className="fa-solid fa-triangle-exclamation" style={{ marginRight: '8px' }}></i>Xác nhận xóa</h2>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom: '20px', lineHeight: '1.6' }}>
                Bạn có chắc chắn muốn xóa tài khoản <strong>#{deleteConfirmId}</strong>?<br/>
                <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.9rem' }}>Hành động này không thể hoàn tác.</span>
              </p>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={() => setDeleteConfirmId(null)}
                  className="btn-secondary"
                  style={{ flex: 1 }}
                  disabled={deleteLoading}
                >
                  Hủy
                </button>
                <button
                  onClick={() => handleDeleteUser(deleteConfirmId)}
                  style={{ flex: 1, backgroundColor: '#ef4444', border: 'none', color: '#fff' }}
                  disabled={deleteLoading}
                >
                  {deleteLoading ? <i className="fa-solid fa-spinner fa-spin"></i> : <><i className="fa-solid fa-trash-can" style={{ marginRight: '6px' }}></i>Xóa</>}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
