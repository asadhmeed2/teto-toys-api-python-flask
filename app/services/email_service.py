import os
import requests


def send_password_reset_email(to_email: str, reset_link: str, api_key: str, from_email: str) -> None:
    """Send a password reset email via Resend."""
    html = f"""
        <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px;">
          <h2 style="color: #0f172a; margin-bottom: 8px;">Reset your password</h2>
          <p style="color: #475569; margin-bottom: 24px;">
            Click the button below to choose a new password. This link expires in <strong>15 minutes</strong>.
          </p>
          <a href="{reset_link}"
             style="display: inline-block; padding: 14px 28px; background: linear-gradient(135deg, #08b880, #00d4aa);
                    color: #fff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
            Reset Password
          </a>
          <p style="color: #94a3b8; font-size: 13px; margin-top: 24px;">
            If you didn't request this, you can safely ignore this email.
          </p>
        </div>
    """
    response = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={'from': from_email, 'to': [to_email], 'subject': 'Reset your TatoToys password', 'html': html},
        timeout=10,
    )
    if not response.ok:
        raise Exception(f'Resend API error {response.status_code}: {response.text}')
