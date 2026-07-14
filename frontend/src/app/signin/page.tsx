'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { API_BASE } from '@/lib/api';

type FormMode = 'register' | 'verify_otp';

export default function SignInPage() {
  const router = useRouter();
  const [mode, setMode] = useState<FormMode>('register');

  // Input fields
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // OTP fields
  const [otp, setOtp] = useState('');
  const [otpSentMessage, setOtpSentMessage] = useState('');
  const [resendTimer, setResendTimer] = useState(0);

  // Feedback states
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Countdown timer for OTP resend
  useEffect(() => {
    if (resendTimer > 0) {
      const interval = setInterval(() => {
        setResendTimer((prev) => prev - 1);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [resendTimer]);

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

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        throw new Error('Máy chủ không phản hồi. Vui lòng thử lại sau.');
      }

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

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        throw new Error('Máy chủ không phản hồi. Vui lòng thử lại sau.');
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Xác thực OTP thất bại.');
      }

      setIsLoading(false);
      window.location.href = '/login';
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

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        throw new Error('Máy chủ không phản hồi. Vui lòng thử lại sau.');
      }

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

  return (
    <div className="waze-login-root">
      {/* ─── Floating Clouds ─── */}
      <div className="waze-clouds">
        <div className="waze-cloud waze-cloud-1">
          <svg width="120" height="50" viewBox="0 0 120 50" fill="none">
            <ellipse cx="60" cy="32" rx="50" ry="16" fill="#fff"/>
            <ellipse cx="38" cy="24" rx="28" ry="18" fill="#fff"/>
            <ellipse cx="78" cy="26" rx="24" ry="14" fill="#fff"/>
            <ellipse cx="56" cy="18" rx="22" ry="14" fill="#fff"/>
          </svg>
        </div>
        <div className="waze-cloud waze-cloud-2">
          <svg width="100" height="42" viewBox="0 0 100 42" fill="none">
            <ellipse cx="50" cy="28" rx="42" ry="13" fill="#fff"/>
            <ellipse cx="32" cy="20" rx="22" ry="15" fill="#fff"/>
            <ellipse cx="65" cy="22" rx="20" ry="12" fill="#fff"/>
          </svg>
        </div>
        <div className="waze-cloud waze-cloud-3">
          <svg width="80" height="36" viewBox="0 0 80 36" fill="none">
            <ellipse cx="40" cy="24" rx="35" ry="11" fill="#fff"/>
            <ellipse cx="26" cy="17" rx="18" ry="12" fill="#fff"/>
            <ellipse cx="54" cy="18" rx="16" ry="10" fill="#fff"/>
          </svg>
        </div>
        <div className="waze-cloud waze-cloud-4">
          <svg width="90" height="38" viewBox="0 0 90 38" fill="none">
            <ellipse cx="45" cy="26" rx="38" ry="12" fill="#fff"/>
            <ellipse cx="30" cy="18" rx="20" ry="13" fill="#fff"/>
            <ellipse cx="60" cy="20" rx="18" ry="11" fill="#fff"/>
          </svg>
        </div>
        <div className="waze-cloud waze-cloud-5">
          <svg width="70" height="32" viewBox="0 0 70 32" fill="none">
            <ellipse cx="35" cy="22" rx="30" ry="10" fill="#fff"/>
            <ellipse cx="22" cy="15" rx="16" ry="11" fill="#fff"/>
            <ellipse cx="48" cy="16" rx="14" ry="9" fill="#fff"/>
          </svg>
        </div>
      </div>

      <div className="waze-login-container">
        {/* ─── Left Branding Panel ─── */}
        <div className="waze-login-left">
          <div className="waze-brand-logo">
            <i className="fa-solid fa-car-side"></i>
            <span>Vietnam LPR</span>
          </div>
          <h1 className="waze-brand-title">NHẬN DIỆN<br/>BIỂN SỐ XE</h1>
          <p className="waze-brand-desc">
            Hệ thống AI nhận diện tự động biển số xe từ camera thời gian thực, ảnh và video với độ chính xác cao.
          </p>

          {/* ─── Animated Road Scene ─── */}
          <div className="waze-road-scene">
            <svg className="waze-road-svg" viewBox="0 0 360 160" fill="none">
              {/* Road */}
              <path d="M-20,120 C60,120 100,55 180,55 C260,55 300,120 380,120"
                    stroke="rgba(255,255,255,0.35)" strokeWidth="28" strokeLinecap="round" fill="none"/>
              <path d="M-20,120 C60,120 100,55 180,55 C260,55 300,120 380,120"
                    stroke="rgba(255,255,255,0.15)" strokeWidth="2" strokeDasharray="8 8" fill="none"/>

              {/* Car 1 - Yellow taxi */}
              <g className="waze-car-group">
                <rect x="-16" y="-10" width="32" height="16" rx="5" fill="#FFD93D" stroke="#E6B800" strokeWidth="1"/>
                <rect x="-12" y="-16" width="20" height="10" rx="4" fill="#FFE566" stroke="#E6B800" strokeWidth="0.8"/>
                <rect x="-9" y="-14" width="14" height="7" rx="2" fill="rgba(135,206,250,0.5)"/>
                <circle cx="-8" cy="8" r="4" fill="#333"/>
                <circle cx="8" cy="8" r="4" fill="#333"/>
                <rect x="-14" y="-4" width="5" height="3" rx="1" fill="#FFF" opacity="0.8"/>
                <rect x="9" y="-4" width="5" height="3" rx="1" fill="#FFF" opacity="0.8"/>
              </g>

              {/* Car 2 - Red car */}
              <g className="waze-car-group-2">
                <rect x="-14" y="-9" width="28" height="14" rx="5" fill="#FF6B6B" stroke="#E05555" strokeWidth="1"/>
                <rect x="-10" y="-14" width="18" height="9" rx="3" fill="#FF8A8A" stroke="#E05555" strokeWidth="0.8"/>
                <rect x="-7" y="-12" width="12" height="6" rx="2" fill="rgba(135,206,250,0.5)"/>
                <circle cx="-7" cy="7" r="3.5" fill="#333"/>
                <circle cx="7" cy="7" r="3.5" fill="#333"/>
                <rect x="-12" y="-3" width="4" height="2.5" rx="1" fill="#FFF" opacity="0.8"/>
                <rect x="8" y="-3" width="4" height="2.5" rx="1" fill="#FFF" opacity="0.8"/>
              </g>

              {/* Car 3 - Green car */}
              <g className="waze-car-group-3">
                <rect x="-12" y="-8" width="24" height="13" rx="4" fill="#4CAF50" stroke="#3D8B40" strokeWidth="1"/>
                <rect x="-8" y="-13" width="16" height="8" rx="3" fill="#66BB6A" stroke="#3D8B40" strokeWidth="0.8"/>
                <rect x="-6" y="-11" width="10" height="5" rx="2" fill="rgba(135,206,250,0.5)"/>
                <circle cx="-6" cy="6" r="3" fill="#333"/>
                <circle cx="6" cy="6" r="3" fill="#333"/>
                <rect x="-10" y="-2" width="3.5" height="2" rx="1" fill="#FFF" opacity="0.8"/>
                <rect x="7" y="-2" width="3.5" height="2" rx="1" fill="#FFF" opacity="0.8"/>
              </g>
            </svg>
          </div>

          {/* ─── Feature Tags ─── */}
          <div className="waze-tags">
            <div className="waze-tag">
              <i className="fa-solid fa-microchip"></i>
              <span>YOLOv8</span>
            </div>
            <div className="waze-tag">
              <i className="fa-solid fa-bolt"></i>
              <span>Realtime</span>
            </div>
            <div className="waze-tag">
              <i className="fa-solid fa-bullseye"></i>
              <span>Accurate</span>
            </div>
          </div>
        </div>

        {/* ─── Right Form Panel ─── */}
        <div className="waze-login-right">
          <div className="waze-form-inner">

            {/* ═══ REGISTER MODE ═══ */}
            {mode === 'register' && (
              <>
                <div className="waze-form-header">
                  <div className="waze-form-icon">
                    <i className="fa-solid fa-user-plus"></i>
                  </div>
                  <h2 className="waze-form-title">Đăng ký tài khoản</h2>
                </div>
                <p className="waze-form-subtitle">Tạo tài khoản mới để sử dụng hệ thống</p>

                <form onSubmit={handleRegisterSubmit} className="waze-form">
                  <div className="waze-field">
                    <label className="waze-field-label">
                      <i className="fa-regular fa-user"></i> Tên tài khoản
                    </label>
                    <input
                      type="text"
                      className="waze-input"
                      placeholder="Nhập tài khoản đăng nhập mới"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                      disabled={isLoading}
                    />
                  </div>

                  <div className="waze-field">
                    <label className="waze-field-label">
                      <i className="fa-regular fa-envelope"></i> Gmail nhận OTP
                    </label>
                    <input
                      type="email"
                      className="waze-input"
                      placeholder="example@gmail.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      disabled={isLoading}
                    />
                  </div>

                  <div className="waze-field">
                    <label className="waze-field-label">
                      <i className="fa-solid fa-lock"></i> Mật khẩu
                    </label>
                    <div className="waze-password-wrapper">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        className="waze-input"
                        placeholder="Nhập mật khẩu mới"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        disabled={isLoading}
                      />
                      <button
                        type="button"
                        className="waze-password-toggle"
                        onClick={() => setShowPassword(!showPassword)}
                        tabIndex={-1}
                      >
                        <i className={`fa-solid ${showPassword ? 'fa-eye-slash' : 'fa-eye'}`}></i>
                      </button>
                    </div>
                  </div>

                  <div className="waze-field">
                    <label className="waze-field-label">
                      <i className="fa-solid fa-lock"></i> Nhập lại mật khẩu
                    </label>
                    <div className="waze-password-wrapper">
                      <input
                        type={showConfirmPassword ? 'text' : 'password'}
                        className="waze-input"
                        placeholder="Xác nhận lại mật khẩu"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        required
                        disabled={isLoading}
                      />
                      <button
                        type="button"
                        className="waze-password-toggle"
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                        tabIndex={-1}
                      >
                        <i className={`fa-solid ${showConfirmPassword ? 'fa-eye-slash' : 'fa-eye'}`}></i>
                      </button>
                    </div>
                  </div>

                  {error && (
                    <div className="waze-alert waze-alert-error">
                      <i className="fa-solid fa-triangle-exclamation"></i>
                      <span>{error}</span>
                    </div>
                  )}

                  <button type="submit" className="waze-submit-btn" disabled={isLoading}>
                    {isLoading ? (
                      <>
                        <div className="waze-spinner"></div>
                        Đang xử lý...
                      </>
                    ) : (
                      <>
                        <i className="fa-solid fa-user-plus"></i>
                        Đăng ký và gửi OTP kích hoạt
                      </>
                    )}
                  </button>

                  <div className="waze-switch-mode">
                    <span>Đã có tài khoản? </span>
                    <button
                      type="button"
                      onClick={() => { window.location.href = '/login'; }}
                    >
                      Đăng nhập
                    </button>
                  </div>
                </form>
              </>
            )}

            {/* ═══ VERIFY OTP MODE ═══ */}
            {mode === 'verify_otp' && (
              <>
                <div className="waze-form-header">
                  <div className="waze-form-icon">
                    <i className="fa-solid fa-shield-halved"></i>
                  </div>
                  <h2 className="waze-form-title">Xác thực tài khoản</h2>
                </div>
                <p className="waze-form-subtitle">Nhập mã OTP đã gửi về Gmail của bạn</p>

                <form onSubmit={handleVerifyOtpSubmit} className="waze-form">
                  {otpSentMessage && otpSentMessage.includes('[Dev Mode]') ? (
                    <div className="waze-alert waze-alert-warning">
                      <i className="fa-solid fa-terminal"></i>
                      <div>
                        <strong>Chế độ Development</strong>
                        <span> — SMTP chưa cấu hình. Kiểm tra <b>terminal backend</b> để lấy mã OTP.</span>
                      </div>
                    </div>
                  ) : (
                    <div className="waze-alert waze-alert-info">
                      <i className="fa-regular fa-paper-plane"></i>
                      <span>{otpSentMessage || 'Một mã xác thực đã được gửi về Gmail của bạn.'}</span>
                    </div>
                  )}

                  <div className="waze-field">
                    <label className="waze-field-label">
                      <i className="fa-solid fa-key"></i> Mã OTP (6 số)
                    </label>
                    <input
                      type="text"
                      maxLength={6}
                      pattern="\d{6}"
                      className="waze-input waze-input-otp"
                      placeholder="------"
                      value={otp}
                      onChange={(e) => setOtp(e.target.value)}
                      required
                      disabled={isLoading}
                    />
                  </div>

                  {error && (
                    <div className="waze-alert waze-alert-error">
                      <i className="fa-solid fa-triangle-exclamation"></i>
                      <span>{error}</span>
                    </div>
                  )}

                  <button type="submit" className="waze-submit-btn" disabled={isLoading}>
                    {isLoading ? (
                      <>
                        <div className="waze-spinner"></div>
                        Đang kích hoạt...
                      </>
                    ) : (
                      <>
                        <i className="fa-solid fa-shield-halved"></i>
                        Kích hoạt tài khoản
                      </>
                    )}
                  </button>

                  <div className="waze-switch-row">
                    <button
                      type="button"
                      className="waze-switch-link"
                      onClick={() => { setMode('register'); setError(''); setSuccessMsg(''); }}
                      disabled={isLoading}
                    >
                      <i className="fa-solid fa-arrow-left"></i> Quay lại
                    </button>
                    <button
                      type="button"
                      className={`waze-resend-btn ${resendTimer > 0 ? 'disabled' : ''}`}
                      onClick={handleResendOtp}
                      disabled={resendTimer > 0 || isLoading}
                    >
                      {resendTimer > 0 ? `Gửi lại (${resendTimer}s)` : 'Gửi lại OTP'}
                    </button>
                  </div>
                </form>
              </>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
