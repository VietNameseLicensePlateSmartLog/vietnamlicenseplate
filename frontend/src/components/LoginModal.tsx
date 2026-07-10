'use client';

import { useState, useEffect } from 'react';
import { API_BASE } from '@/lib/api';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (user: { id: number; username: string; role: string }) => void;
  initialMode?: ModalMode;
  embedded?: boolean;
}

type ModalMode = 'login' | 'register' | 'verify_otp' | 'forgot_password' | 'reset_password';

export default function LoginModal({ isOpen, onClose, onLoginSuccess, initialMode = 'login', embedded = false }: LoginModalProps) {
  const [mode, setMode] = useState<ModalMode>(initialMode);

  // Input fields
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // OTP and Reset Password fields
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);

  // Feedback states
  const [otpSentMessage, setOtpSentMessage] = useState('');
  const [resendTimer, setResendTimer] = useState(0);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Clear states when modal opens or closes
  useEffect(() => {
    if (!isOpen) {
      setError('');
      setSuccessMsg('');
      setIsLoading(false);
      setMode(initialMode);
      setUsername('');
      setEmail('');
      setPassword('');
      setConfirmPassword('');
      setOtp('');
      setNewPassword('');
      setConfirmNewPassword('');
      setShowPassword(false);
      setShowConfirmPassword(false);
      setShowNewPassword(false);
    }
  }, [isOpen]);

  // Countdown timer for OTP resend
  useEffect(() => {
    if (resendTimer > 0) {
      const interval = setInterval(() => {
        setResendTimer((prev) => prev - 1);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [resendTimer]);

  if (!isOpen) return null;

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Đăng nhập thất bại.');
      }

      setIsLoading(false);
      onLoginSuccess({ id: data.user.id, username: data.user.username, role: data.user.role });
      setUsername('');
      setPassword('');
      onClose();
    } catch (err: any) {
      setIsLoading(false);
      setError(err.message || 'Đã có lỗi xảy ra.');
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    if (password !== confirmPassword) {
      setError('Mật khẩu nhập lại không khớp.');
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Đăng ký thất bại.');
      }

      setIsLoading(false);
      setOtpSentMessage(data.message);
      setMode('verify_otp');
      setResendTimer(30);
    } catch (err: any) {
      setIsLoading(false);
      setError(err.message || 'Đã có lỗi xảy ra.');
    }
  };

  const handleVerifyOtpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, otp }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Xác thực OTP thất bại.');
      }

      setIsLoading(false);
      setSuccessMsg('Kích hoạt tài khoản thành công! Bạn có thể đăng nhập ngay.');
      setMode('login');
      setEmail('');
      setPassword('');
      setConfirmPassword('');
      setOtp('');
    } catch (err: any) {
      setIsLoading(false);
      setError(err.message || 'Mã OTP không hợp lệ hoặc đã hết hạn.');
    }
  };

  const handleResendOtp = async () => {
    if (resendTimer > 0) return;
    setError('');
    setSuccessMsg('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/auth/resend-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Gửi lại mã OTP thất bại.');
      }

      setIsLoading(false);
      setOtpSentMessage(data.message);
      setResendTimer(30);
    } catch (err: any) {
      setIsLoading(false);
      setError(err.message || 'Đã có lỗi xảy ra.');
    }
  };

  const handleForgotPasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Yêu cầu thất bại.');
      }

      setIsLoading(false);
      setOtpSentMessage(data.message);
      setMode('reset_password');
      setResendTimer(30);
    } catch (err: any) {
      setIsLoading(false);
      setError(err.message || 'Tài khoản không tồn tại hoặc lỗi hệ thống.');
    }
  };

  const handleResetPasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    if (newPassword !== confirmNewPassword) {
      setError('Mật khẩu mới nhập lại không khớp.');
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, otp, new_password: newPassword }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Đặt lại mật khẩu thất bại.');
      }

      setIsLoading(false);
      setSuccessMsg('Đổi mật khẩu thành công! Hãy đăng nhập bằng mật khẩu mới.');
      setMode('login');
      setOtp('');
      setNewPassword('');
      setConfirmNewPassword('');
    } catch (err: any) {
      setIsLoading(false);
      setError(err.message || 'Mã OTP không hợp lệ hoặc đã hết hạn.');
    }
  };

  const handleResendForgotPasswordOtp = async () => {
    if (resendTimer > 0) return;
    setError('');
    setSuccessMsg('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Gửi lại OTP thất bại.');
      }

      setIsLoading(false);
      setOtpSentMessage(data.message);
      setResendTimer(30);
    } catch (err: any) {
      setIsLoading(false);
      setError(err.message || 'Đã có lỗi xảy ra.');
    }
  };

  /* ─── Left Branding Panel (login mode only) ─── */
  const renderBrandingPanel = () => (
    <div className="login-branding">
      <div className="login-branding-content">
        <div className="login-brand-logo">
          <i className="fa-solid fa-car-side"></i>
          <span>Vietnam LPR</span>
        </div>
        <div className="login-brand-subtitle">HỆ THỐNG AI</div>
        <h1 className="login-brand-title">NHẬN DIỆN BIỂN SỐ</h1>
        <p className="login-brand-desc">
          Phân tích hình ảnh, video và dữ liệu camera thời gian thực với độ chính xác cao dựa trên mô hình YOLOv8.
        </p>

        {/* Animated Car with Laser Scan */}
        <div className="login-car-scene">
          <div className="login-car-wrapper">
            {/* Car SVG */}
            <svg className="login-car-svg" viewBox="0 0 340 220" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* Ground shadow */}
              <ellipse cx="170" cy="205" rx="130" ry="8" fill="rgba(0,0,0,0.3)"/>

              {/* ── Wheels ── */}
              <circle cx="80" cy="185" r="22" fill="#1a1a1a" stroke="#333" strokeWidth="2"/>
              <circle cx="80" cy="185" r="14" fill="#3a3a3a"/>
              <circle cx="80" cy="185" r="6" fill="#666"/>
              <circle cx="260" cy="185" r="22" fill="#1a1a1a" stroke="#333" strokeWidth="2"/>
              <circle cx="260" cy="185" r="14" fill="#3a3a3a"/>
              <circle cx="260" cy="185" r="6" fill="#666"/>

              {/* ── Body lower (bumper area) ── */}
              <rect x="35" y="135" width="270" height="40" rx="12" fill="#E8A800"/>

              {/* ── Body main ── */}
              <rect x="42" y="100" width="256" height="42" rx="10" fill="#F5C518" stroke="#D4A800" strokeWidth="1.5"/>

              {/* ── Cabin ── */}
              <path d="M88 100 L110 58 Q116 46 132 42 L208 42 Q224 46 230 58 L252 100 Z" fill="#FFD940" stroke="#D4A800" strokeWidth="1.5"/>

              {/* ── Roof ── */}
              <path d="M110 58 Q116 44 136 38 L204 38 Q224 44 230 58 Z" fill="#FFD940" stroke="#D4A800" strokeWidth="1"/>

              {/* ── Windshield ── */}
              <path d="M96 98 L116 56 Q118 50 128 48 L212 48 Q222 50 224 56 L244 98 Z" fill="rgba(120,200,255,0.3)" stroke="rgba(100,200,255,0.5)" strokeWidth="1.5"/>
              {/* Glass reflection */}
              <path d="M108 92 L124 58 L145 58 L130 92 Z" fill="rgba(255,255,255,0.08)"/>
              {/* Window divider */}
              <line x1="170" y1="46" x2="170" y2="98" stroke="rgba(100,200,255,0.35)" strokeWidth="1"/>

              {/* ── Headlight left ── */}
              <rect x="42" y="110" width="38" height="20" rx="7" fill="#FFF" opacity="0.95"/>
              <rect x="46" y="113" width="30" height="14" rx="5" fill="#FFFDE0"/>
              <rect x="50" y="116" width="22" height="8" rx="4" fill="#FFF" opacity="0.6"/>
              {/* ── Headlight right ── */}
              <rect x="260" y="110" width="38" height="20" rx="7" fill="#FFF" opacity="0.95"/>
              <rect x="264" y="113" width="30" height="14" rx="5" fill="#FFFDE0"/>
              <rect x="268" y="116" width="22" height="8" rx="4" fill="#FFF" opacity="0.6"/>

              {/* ── Grille ── */}
              <rect x="138" y="120" width="64" height="16" rx="5" fill="#C49A00" stroke="#B08A00" strokeWidth="0.8"/>
              <line x1="150" y1="121" x2="150" y2="135" stroke="#B08A00" strokeWidth="0.7"/>
              <line x1="162" y1="121" x2="162" y2="135" stroke="#B08A00" strokeWidth="0.7"/>
              <line x1="178" y1="121" x2="178" y2="135" stroke="#B08A00" strokeWidth="0.7"/>
              <line x1="190" y1="121" x2="190" y2="135" stroke="#B08A00" strokeWidth="0.7"/>

              {/* ── Front bumper ── */}
              <rect x="55" y="150" width="230" height="12" rx="6" fill="#D4A800"/>

              {/* ── License plate ── */}
              <rect x="125" y="153" width="90" height="28" rx="4" fill="#FFF" stroke="#DDD" strokeWidth="1"/>
              <text x="170" y="172" textAnchor="middle" fontSize="12" fontWeight="bold" fill="#003366" fontFamily="monospace">30F-181.12</text>

              {/* ── Detection bounding box (dashed) ── */}
              <rect x="120" y="148" width="100" height="38" rx="4" fill="none" stroke="rgba(0,255,136,0.5)" strokeWidth="1.5" strokeDasharray="4 3"/>

              {/* ── Corner brackets on plate ── */}
              <path d="M122 153 L122 149 L128 149" fill="none" stroke="#00ff88" strokeWidth="1.5"/>
              <path d="M218 153 L218 149 L212 149" fill="none" stroke="#00ff88" strokeWidth="1.5"/>
              <path d="M122 187 L122 191 L128 191" fill="none" stroke="#00ff88" strokeWidth="1.5"/>
              <path d="M218 187 L218 191 L212 191" fill="none" stroke="#00ff88" strokeWidth="1.5"/>
            </svg>

            {/* Laser scan line — sweeps top to bottom */}
            <div className="login-laser-beam"></div>
            <div className="login-laser-glow"></div>

            {/* Scan result popup */}
            <div className="login-scan-result">
              <div className="login-scan-badge">
                <i className="fa-solid fa-check"></i>
              </div>
              <span>30F-181.12</span>
            </div>
          </div>

          {/* Tech feature tags */}
          <div className="login-car-tags">
            <div className="login-car-tag">
              <i className="fa-solid fa-microchip"></i>
              <span>YOLOv8</span>
            </div>
            <div className="login-car-tag">
              <i className="fa-solid fa-bolt"></i>
              <span>Realtime</span>
            </div>
          </div>
        </div>
      </div>

      {/* Decorative grid */}
      <div className="login-branding-grid"></div>
    </div>
  );

  /* ─── Right Form Panel ─── */
  const renderFormPanel = () => (
    <div className="login-form-panel">
      <div className="login-form-inner">
        {/* Close button (hidden in embedded mode) */}
        {!embedded && (
          <button className="login-close-btn" onClick={onClose}>
            <i className="fa-solid fa-xmark"></i>
          </button>
        )}

        {/* LOGIN MODE */}
        {mode === 'login' && (
          <>
            <h2 className="login-form-title">Đăng nhập hệ thống</h2>

            <form onSubmit={handleLoginSubmit} className="login-form">
              {successMsg && (
                <div className="login-alert login-alert-success">
                  <i className="fa-solid fa-circle-check"></i>
                  <span>{successMsg}</span>
                </div>
              )}

              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-regular fa-user"></i> Tài khoản đăng nhập:
                </label>
                <input
                  type="text"
                  className="login-input"
                  placeholder="Nhập tên tài khoản"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-solid fa-lock"></i> Mật khẩu:
                </label>
                <div className="login-password-wrapper">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    className="login-input"
                    placeholder="Nhập mật khẩu"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    className="login-password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                  >
                    <i className={`fa-solid ${showPassword ? 'fa-eye-slash' : 'fa-eye'}`}></i>
                  </button>
                </div>
              </div>

              {error && (
                <div className="login-alert login-alert-error">
                  <i className="fa-solid fa-triangle-exclamation"></i>
                  <span>{error}</span>
                </div>
              )}

              <div className="login-forgot-link">
                <button
                  type="button"
                  onClick={() => { setMode('forgot_password'); setError(''); setSuccessMsg(''); }}
                >
                  Quên mật khẩu?
                </button>
              </div>

              <button type="submit" className="login-submit-btn" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <div className="small-spinner" style={{ marginRight: '0.5rem' }}></div>
                    Đang đăng nhập...
                  </>
                ) : (
                  'Đăng nhập'
                )}
              </button>

              <div className="login-switch-mode">
                <span>Chưa có tài khoản? </span>
                <button
                  type="button"
                  onClick={() => {
                    if (typeof window !== 'undefined' && window.location.pathname === '/login') {
                      window.location.href = '/signin';
                    } else {
                      setMode('register');
                      setError('');
                      setSuccessMsg('');
                    }
                  }}
                >
                  Đăng ký ngay
                </button>
              </div>
            </form>
          </>
        )}

        {/* REGISTER MODE */}
        {mode === 'register' && (
          <>
            <h2 className="login-form-title">Đăng ký tài khoản</h2>

            <form onSubmit={handleRegisterSubmit} className="login-form">
              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-regular fa-user"></i> Tên tài khoản đăng ký:
                </label>
                <input
                  type="text"
                  className="login-input"
                  placeholder="Nhập tài khoản đăng nhập mới"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-regular fa-envelope"></i> Gmail nhận OTP kích hoạt:
                </label>
                <input
                  type="email"
                  className="login-input"
                  placeholder="nhap_gmail_cua_ban@gmail.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-solid fa-lock"></i> Mật khẩu:
                </label>
                <div className="login-password-wrapper">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    className="login-input"
                    placeholder="Nhập mật khẩu mới"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    className="login-password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                  >
                    <i className={`fa-solid ${showPassword ? 'fa-eye-slash' : 'fa-eye'}`}></i>
                  </button>
                </div>
              </div>

              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-solid fa-lock"></i> Nhập lại mật khẩu:
                </label>
                <div className="login-password-wrapper">
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    className="login-input"
                    placeholder="Xác nhận lại mật khẩu"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    className="login-password-toggle"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    tabIndex={-1}
                  >
                    <i className={`fa-solid ${showConfirmPassword ? 'fa-eye-slash' : 'fa-eye'}`}></i>
                  </button>
                </div>
              </div>

              {error && (
                <div className="login-alert login-alert-error">
                  <i className="fa-solid fa-triangle-exclamation"></i>
                  <span>{error}</span>
                </div>
              )}

              <button type="submit" className="login-submit-btn" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <div className="small-spinner" style={{ marginRight: '0.5rem' }}></div>
                    Đang xử lý...
                  </>
                ) : (
                  'Đăng ký và gửi OTP kích hoạt'
                )}
              </button>

              <div className="login-switch-mode">
                <span>Đã có tài khoản? </span>
                <button
                  type="button"
                  onClick={() => {
                    if (typeof window !== 'undefined' && window.location.pathname === '/signin') {
                      window.location.href = '/login';
                    } else {
                      setMode('login');
                      setError('');
                      setSuccessMsg('');
                    }
                  }}
                >
                  Đăng nhập
                </button>
              </div>
            </form>
          </>
        )}

        {/* VERIFY OTP MODE */}
        {mode === 'verify_otp' && (
          <>
            <h2 className="login-form-title">Xác thực tài khoản</h2>

            <form onSubmit={handleVerifyOtpSubmit} className="login-form">
              {otpSentMessage && otpSentMessage.includes('[Dev Mode]') ? (
                <div className="login-alert login-alert-warning">
                  <i className="fa-solid fa-terminal"></i>
                  <div>
                    <strong>Chế độ Development</strong>
                    <span> — SMTP chưa cấu hình. Kiểm tra <b>terminal backend</b> để lấy mã OTP.</span>
                  </div>
                </div>
              ) : (
                <div className="login-alert login-alert-info">
                  <i className="fa-regular fa-paper-plane"></i>
                  <span>{otpSentMessage || 'Một mã xác thực đã được gửi về Gmail của bạn.'}</span>
                </div>
              )}

              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-solid fa-key"></i> Nhập mã OTP xác thực (6 số):
                </label>
                <input
                  type="text"
                  maxLength={6}
                  pattern="\d{6}"
                  className="login-input login-input-otp"
                  placeholder="------"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              {error && (
                <div className="login-alert login-alert-error">
                  <i className="fa-solid fa-triangle-exclamation"></i>
                  <span>{error}</span>
                </div>
              )}

              <button type="submit" className="login-submit-btn" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <div className="small-spinner" style={{ marginRight: '0.5rem' }}></div>
                    Đang kích hoạt...
                  </>
                ) : (
                  'Kích hoạt tài khoản'
                )}
              </button>

              <div className="login-switch-row">
                <button
                  type="button"
                  className="login-switch-link"
                  onClick={() => { setMode('register'); setError(''); setSuccessMsg(''); }}
                  disabled={isLoading}
                >
                  Quay lại đăng ký
                </button>
                <button
                  type="button"
                  className={`login-resend-btn ${resendTimer > 0 ? 'disabled' : ''}`}
                  onClick={handleResendOtp}
                  disabled={resendTimer > 0 || isLoading}
                >
                  {resendTimer > 0 ? `Gửi lại OTP (${resendTimer}s)` : 'Gửi lại mã OTP'}
                </button>
              </div>
            </form>
          </>
        )}

        {/* FORGOT PASSWORD MODE */}
        {mode === 'forgot_password' && (
          <>
            <h2 className="login-form-title">Khôi phục mật khẩu</h2>

            <form onSubmit={handleForgotPasswordSubmit} className="login-form">
              <div className="login-alert login-alert-info">
                Nhập tài khoản đăng nhập của bạn. Hệ thống sẽ gửi một mã OTP khôi phục về hòm thư Gmail mà bạn đã liên kết với tài khoản này khi đăng ký.
              </div>

              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-regular fa-user"></i> Tài khoản của bạn:
                </label>
                <input
                  type="text"
                  className="login-input"
                  placeholder="Nhập tên tài khoản cần lấy lại mật khẩu"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              {error && (
                <div className="login-alert login-alert-error">
                  <i className="fa-solid fa-triangle-exclamation"></i>
                  <span>{error}</span>
                </div>
              )}

              <button type="submit" className="login-submit-btn" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <div className="small-spinner" style={{ marginRight: '0.5rem' }}></div>
                    Đang xử lý...
                  </>
                ) : (
                  'Gửi mã OTP qua Gmail'
                )}
              </button>

              <div className="login-switch-mode" style={{ borderTop: 'none', paddingTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => { setMode('login'); setError(''); setSuccessMsg(''); }}
                >
                  Quay lại đăng nhập
                </button>
              </div>
            </form>
          </>
        )}

        {/* RESET PASSWORD MODE */}
        {mode === 'reset_password' && (
          <>
            <h2 className="login-form-title">Đặt lại mật khẩu mới</h2>

            <form onSubmit={handleResetPasswordSubmit} className="login-form">
              {otpSentMessage && otpSentMessage.includes('[Dev Mode]') ? (
                <div className="login-alert login-alert-warning">
                  <i className="fa-solid fa-terminal"></i>
                  <div>
                    <strong>Chế độ Development</strong>
                    <span> — SMTP chưa cấu hình. Kiểm tra <b>terminal backend</b> để lấy mã OTP.</span>
                  </div>
                </div>
              ) : (
                <div className="login-alert login-alert-info">
                  <i className="fa-regular fa-paper-plane"></i>
                  <span>{otpSentMessage || 'Mã OTP đặt lại mật khẩu đã được gửi về Gmail của bạn.'}</span>
                </div>
              )}

              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-solid fa-key"></i> Nhập mã OTP (6 số):
                </label>
                <input
                  type="text"
                  maxLength={6}
                  pattern="\d{6}"
                  className="login-input login-input-otp"
                  placeholder="------"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-solid fa-lock"></i> Mật khẩu mới:
                </label>
                <div className="login-password-wrapper">
                  <input
                    type={showNewPassword ? 'text' : 'password'}
                    className="login-input"
                    placeholder="Nhập mật khẩu mới"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    className="login-password-toggle"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    tabIndex={-1}
                  >
                    <i className={`fa-solid ${showNewPassword ? 'fa-eye-slash' : 'fa-eye'}`}></i>
                  </button>
                </div>
              </div>

              <div className="login-field">
                <label className="login-field-label">
                  <i className="fa-solid fa-lock"></i> Xác nhận mật khẩu mới:
                </label>
                <div className="login-password-wrapper">
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    className="login-input"
                    placeholder="Nhập lại mật khẩu mới"
                    value={confirmNewPassword}
                    onChange={(e) => setConfirmNewPassword(e.target.value)}
                    required
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    className="login-password-toggle"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    tabIndex={-1}
                  >
                    <i className={`fa-solid ${showConfirmPassword ? 'fa-eye-slash' : 'fa-eye'}`}></i>
                  </button>
                </div>
              </div>

              {error && (
                <div className="login-alert login-alert-error">
                  <i className="fa-solid fa-triangle-exclamation"></i>
                  <span>{error}</span>
                </div>
              )}

              <button type="submit" className="login-submit-btn" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <div className="small-spinner" style={{ marginRight: '0.5rem' }}></div>
                    Đang xử lý...
                  </>
                ) : (
                  'Xác nhận đổi mật khẩu'
                )}
              </button>

              <div className="login-switch-row">
                <button
                  type="button"
                  className="login-switch-link"
                  onClick={() => { setMode('login'); setError(''); setSuccessMsg(''); }}
                  disabled={isLoading}
                >
                  Hủy & Đăng nhập
                </button>
                <button
                  type="button"
                  className={`login-resend-btn ${resendTimer > 0 ? 'disabled' : ''}`}
                  onClick={handleResendForgotPasswordOtp}
                  disabled={resendTimer > 0 || isLoading}
                >
                  {resendTimer > 0 ? `Gửi lại OTP (${resendTimer}s)` : 'Gửi lại mã OTP'}
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );

  return (
    <div className={embedded ? 'login-page-wrapper' : 'login-modal-overlay'} onClick={(e) => { if (e.target === e.currentTarget && !embedded) onClose(); }}>
      <div className={`login-modal-container ${(mode === 'login' || embedded) ? 'with-branding' : ''}`}>
        {/* Left branding panel - always show in embedded mode, only login in modal */}
        {(embedded || mode === 'login') && renderBrandingPanel()}

        {/* Right form panel */}
        {renderFormPanel()}
      </div>
    </div>
  );
}
