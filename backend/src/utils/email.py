import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.config.settings import settings


def test_smtp_connection(to_email: str, otp: str) -> dict:
    """Test SMTP connection và gửi email test.
    Trả về dict với 'ok' (bool) và 'message' (str)."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        return {
            "ok": False,
            "message": f"SMTP chưa cấu hình. OTP test: {otp}"
        }

    msg = MIMEMultipart()
    msg['From'] = settings.SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = "[TEST] Vietnam LPR - Kiểm tra gửi email"
    body = f"<h3>Email test thành công!</h3><p>Mã OTP test: <b>{otp}</b></p>"
    msg.attach(MIMEText(body, 'html', 'utf-8'))

    server = None
    try:
        print(f"[EMAIL-TEST] Kết nối {settings.SMTP_SERVER}:{settings.SMTP_PORT}...")
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        print(f"[EMAIL-TEST] Đăng nhập với: {settings.SMTP_USER}")
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        print(f"[EMAIL-TEST] ✅ Gửi thành công đến {to_email}")
        return {"ok": True, "message": f"Gửi email test thành công đến {to_email}!"}
    except smtplib.SMTPAuthenticationError as e:
        msg = f"Lỗi xác thực: Sai tài khoản hoặc App Password. Chi tiết: {e}"
        print(f"[EMAIL-TEST] ❌ {msg}")
        return {"ok": False, "message": msg}
    except smtplib.SMTPConnectError as e:
        msg = f"Không thể kết nối {settings.SMTP_SERVER}:{settings.SMTP_PORT}. Chi tiết: {e}"
        print(f"[EMAIL-TEST] ❌ {msg}")
        return {"ok": False, "message": msg}
    except TimeoutError:
        msg = f"Timeout kết nối SMTP ({settings.SMTP_SERVER})"
        print(f"[EMAIL-TEST] ❌ {msg}")
        return {"ok": False, "message": msg}
    except Exception as e:
        msg = f"Lỗi không xác định: {type(e).__name__}: {e}"
        print(f"[EMAIL-TEST] ❌ {msg}")
        return {"ok": False, "message": msg}
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass

def send_otp_email(to_email: str, otp: str):
    """Gửi email OTP xác thực đến người dùng.
    Trả về True nếu gửi thành công, False nếu thất bại."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"[EMAIL] ⚠️ SMTP chưa được cấu hình. OTP cho {to_email} là: {otp}")
        print(f"[EMAIL] 👉 Để gửi email, điền SMTP_USER và SMTP_PASSWORD trong file .env")
        return False

    msg = MIMEMultipart()
    msg['From'] = settings.SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = "Mã OTP xác thực Vietnam LPR"

    body = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px; margin: auto; border: 1px solid #e2e8f0; border-radius: 8px;">
        <h2 style="color: #4f46e5; border-bottom: 2px solid #eef2f6; padding-bottom: 10px;">Xác nhận thao tác trên Vietnam LPR</h2>
        <p>Chào bạn,</p>
        <p>Hệ thống ghi nhận yêu cầu đăng ký hoặc khôi phục tài khoản của bạn.</p>
        <p>Mã OTP xác thực của bạn là:</p>
        <div style="text-align: center; margin: 30px 0;">
            <span style="font-size: 32px; font-weight: bold; color: #4f46e5; letter-spacing: 5px; background-color: #f0fdf4; padding: 10px 25px; border-radius: 6px; border: 1px dashed #86efac;">{otp}</span>
        </div>
        <p>Mã OTP này có hiệu lực trong vòng <b>5 phút</b>. Vui lòng không chia sẻ mã này cho bất kỳ ai khác.</p>
        <hr style="border: 0; border-top: 1px solid #f1f5f9; margin: 30px 0;"/>
        <p style="font-size: 12px; color: #94a3b8; text-align: center;">Trân trọng,<br/>Đội ngũ phát triển Vietnam LPR</p>
    </div>
    """
    msg.attach(MIMEText(body, 'html', 'utf-8'))

    server = None
    try:
        print(f"[EMAIL] Đang kết nối SMTP {settings.SMTP_SERVER}:{settings.SMTP_PORT}...")
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        print(f"[EMAIL] Đang đăng nhập SMTP với tài khoản: {settings.SMTP_USER}")
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        print(f"[EMAIL] ✅ Gửi email OTP thành công đến {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[EMAIL] ❌ Lỗi xác thực SMTP (sai tài khoản hoặc App Password): {e}")
        print(f"[EMAIL] 👉 Kiểm tra: SMTP_USER={settings.SMTP_USER}, SMTP_PASSWORD=***")
        print(f"[EMAIL] 👉 Tạo App Password mới tại: https://myaccount.google.com/apppasswords")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"[EMAIL] ❌ Không thể kết nối SMTP server {settings.SMTP_SERVER}:{settings.SMTP_PORT}: {e}")
        print(f"[EMAIL] 👉 Kiểm tra kết nối internet hoặc firewall")
        return False
    except TimeoutError:
        print(f"[EMAIL] ❌ Timeout khi gửi email đến {to_email} (server: {settings.SMTP_SERVER})")
        return False
    except Exception as e:
        print(f"[EMAIL] ❌ Lỗi khi gửi email OTP đến {to_email}: {type(e).__name__}: {e}")
        return False
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass
