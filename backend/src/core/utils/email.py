import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.core.config.settings import settings

def send_otp_email(to_email: str, otp_code: str, username: str = None) -> bool:
    subject = "Mã OTP xác thực - Vietnam LPR"
    body = f"""
    <html>
    <body style="margin:0; padding:0; background-color:#f4f7fa; font-family: 'Segoe UI', Arial, sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f7fa; padding:30px 0;">
        <tr>
          <td align="center">
            <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:16px; overflow:hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">
              <!-- Header -->
              <tr>
                <td style="background: linear-gradient(135deg, #00b4d8, #0077b6); padding:30px 40px; text-align:center;">
                  <h1 style="color:#ffffff; margin:0; font-size:20px; font-weight:700; letter-spacing:1px;">VIETNAM LPR</h1>
                  <p style="color:rgba(255,255,255,0.85); margin:4px 0 0; font-size:13px;">Nhận diện biển số xe thông minh</p>
                </td>
              </tr>
              <!-- Body -->
              <tr>
                <td style="padding:32px 40px;">
                  <h2 style="color:#1a1a2e; margin:0 0 8px; font-size:20px;">Xác thực tài khoản</h2>
                  <p style="color:#555; margin:0 0 20px; font-size:14px;">Xin chào <b>{username or ''}</b>,</p>
                  <p style="color:#555; margin:0 0 12px; font-size:14px;">Mã OTP xác thực của bạn là:</p>
                  <div style="background:#f0f9ff; border:2px dashed #00b4d8; border-radius:12px; padding:16px 0; text-align:center; margin-bottom:20px;">
                    <span style="color:#0077b6; font-size:36px; font-weight:800; letter-spacing:10px; font-family:monospace;">{otp_code}</span>
                  </div>
                  <p style="color:#888; margin:0; font-size:13px;">⏱ Mã có hiệu lực trong <b>5 phút</b>. Không chia sẻ mã này với bất kỳ ai.</p>
                </td>
              </tr>
              <!-- Footer -->
              <tr>
                <td style="background:#f8fafc; padding:16px 40px; text-align:center; border-top:1px solid #eee;">
                  <p style="color:#aaa; margin:0; font-size:11px;">© 2026 Vietnam LPR — Hệ thống nhận diện biển số xe AI</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    msg = MIMEMultipart('related')
    msg['From'] = f"Viet Nam License Plate AI <{settings.SMTP_USER}>"
    msg['To'] = to_email
    msg['Subject'] = subject

    # Attach HTML body
    msg_alt = MIMEMultipart('alternative')
    msg_alt.attach(MIMEText(body, 'html'))
    msg.attach(msg_alt)

    try:
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"[EMAIL] ❌ SMTP Error: {e}")
        print(f"[EMAIL] 📋 OTP for {to_email}: {otp_code}")
        return False

def test_smtp_connection() -> dict:
    try:
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.quit()
        return {"status": "success", "message": "SMTP connection OK"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
