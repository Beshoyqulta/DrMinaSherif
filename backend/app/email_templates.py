"""Editable HTML templates for Render/Resend notification emails."""

from html import escape


def shell(content: str) -> str:
    return f'''<div style="margin:0;background:#f7f5ef;padding:32px 16px;font-family:Arial,Helvetica,sans-serif;color:#182622;"><div style="max-width:620px;margin:0 auto;background:#ffffff;border:1px solid #e2ddd2;border-radius:16px;overflow:hidden;"><div style="background:#1f4e43;padding:24px 28px;color:#ffffff;"><div style="font-size:12px;letter-spacing:1.4px;text-transform:uppercase;color:#d9eee5;">Private Patient Portal</div><h1 style="margin:8px 0 0;font-family:Georgia,serif;font-size:25px;font-weight:600;">Dr. Mina Sherif</h1></div><div style="padding:28px;line-height:1.6;font-size:15px;">{content}</div><div style="border-top:1px solid #e2ddd2;padding:18px 28px;color:#768780;font-size:12px;line-height:1.5;">This is a private, non-emergency patient portal notification.<br />For urgent psychiatric support, contact local emergency services or Dr. Mina Sherif directly.</div></div></div>'''


def button(label: str, url: str) -> str:
    return f'<a href="{escape(url, quote=True)}" style="display:inline-block;background:#1f4e43;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;">{escape(label)}</a>'


def welcome(name: str, url: str):
    return "Welcome to Dr. Mina Sherif’s Patient Portal", shell(f'<p>Hello {escape(name or "there")},</p><p>Welcome to Dr. Mina Sherif’s Patient Portal. Your registration was received successfully.</p><div style="background:#eef6f1;border-left:4px solid #2e6f5e;padding:14px 16px;margin:20px 0;">Your account is now waiting for Dr. Mina Sherif’s approval.</div><p>Once approved, you will be able to use your private patient portal, emotion journal, doctor channel, clinic feed, and appointment tools.</p><p>{button("Open Patient Portal", url)}</p><p>Thank you,<br />Dr. Mina Sherif’s Clinic</p>')


def approved(name: str, url: str):
    return "Your Dr. Mina Sherif Patient Portal access is approved", shell(f'<p>Hello {escape(name or "there")},</p><p>Dr. Mina Sherif has approved your access to the Patient Portal.</p><div style="background:#eef6f1;border-left:4px solid #2e6f5e;padding:14px 16px;margin:20px 0;">Your private portal access is now active.</div><p>{button("Open Patient Portal", url)}</p><p>Please remember that the private channel is for non-urgent messages only.</p><p>Warmly,<br />Dr. Mina Sherif</p>')


def doctor_message(name: str, url: str):
    return "You have a new private message from Dr. Mina Sherif", shell(f'<p>Hello {escape(name or "there")},</p><p>Dr. Mina Sherif sent you a new private message in your Patient Portal.</p><p>{button("Open Private Channel", url)}</p><p>Please do not use this channel for psychiatric emergencies.</p><p>Dr. Mina Sherif’s Clinic</p>')


def patient_message(name: str, url: str):
    return "A patient sent a new private portal message", shell(f'<p>Hello {escape(name or "Doctor")},</p><p>A patient sent a new private message through the Patient Portal.</p><p>{button("Open Doctor Panel", url.rstrip("/") + "/admin_panel")}</p><p>Dr. Mina Sherif’s Patient Portal</p>')


def appointment_request(name: str, url: str):
    return "New patient appointment request", shell(f'<p>Hello {escape(name or "Doctor")},</p><p>A patient has submitted a new appointment request.</p><p>{button("Review Appointment Request", url.rstrip("/") + "/admin_panel")}</p><p>Dr. Mina Sherif’s Patient Portal</p>')


def appointment_updated(name: str, status: str, url: str):
    return "Your appointment status was updated", shell(f'<p>Hello {escape(name or "there")},</p><p>Your appointment status has been updated to:</p><div style="background:#eef6f1;border-left:4px solid #2e6f5e;padding:14px 16px;margin:20px 0;font-size:18px;font-weight:bold;">{escape(status or "updated")}</div><p>{button("View My Appointments", url.rstrip("/") + "/care")}</p><p>Dr. Mina Sherif’s Clinic</p>')


def clinic_broadcast(name: str, title: str, url: str):
    safe_title = escape(title or "New clinic update from Dr. Mina Sherif")
    return safe_title, shell(f'<p>Hello {escape(name or "there")},</p><p>Dr. Mina Sherif has posted a new update in the Clinic Feed:</p><div style="background:#f7f5ef;border:1px solid #e2ddd2;border-radius:10px;padding:16px;margin:20px 0;"><strong style="font-size:17px;">{safe_title}</strong></div><p>{button("Open Clinic Feed", url.rstrip("/") + "/feed")}</p><p>Dr. Mina Sherif’s Clinic</p>')
