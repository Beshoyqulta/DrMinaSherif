# Dr. Mina Sherif Patient Portal — Email Templates

These templates cover the current email events in the application.

- Supabase Auth templates use Supabase variables such as `{{ .ConfirmationURL }}`.
- Render/Resend notification templates use the placeholders shown in each section. The current backend sends equivalent messages; these are the polished copy and layout to use when replacing the inline HTML.

## Shared visual style

Use this outer structure for Render/Resend emails:

```html
<div style="margin:0;background:#f7f5ef;padding:32px 16px;font-family:Arial,Helvetica,sans-serif;color:#182622;">
  <div style="max-width:620px;margin:0 auto;background:#ffffff;border:1px solid #e2ddd2;border-radius:16px;overflow:hidden;">
    <div style="background:#1f4e43;padding:24px 28px;color:#ffffff;">
      <div style="font-size:12px;letter-spacing:1.4px;text-transform:uppercase;color:#d9eee5;">Private Patient Portal</div>
      <h1 style="margin:8px 0 0;font-family:Georgia,serif;font-size:25px;font-weight:600;">Dr. Mina Sherif</h1>
    </div>
    <div style="padding:28px;line-height:1.6;font-size:15px;">
      <!-- CONTENT GOES HERE -->
    </div>
    <div style="border-top:1px solid #e2ddd2;padding:18px 28px;color:#768780;font-size:12px;line-height:1.5;">
      This is a private, non-emergency patient portal notification.<br />
      For urgent psychiatric support, contact local emergency services or Dr. Mina Sherif directly.
    </div>
  </div>
</div>
```

## 1. Welcome — registration waiting for approval

Use for `profiles INSERT` through the Render/Resend webhook.

Subject:

```text
Welcome to Dr. Mina Sherif’s Patient Portal
```

Placeholders: `{{patient_name}}`, `{{portal_url}}`

Content:

```html
<p>Hello {{patient_name}},</p>
<p>Welcome to Dr. Mina Sherif’s Patient Portal. Your registration was received successfully.</p>
<div style="background:#eef6f1;border-left:4px solid #2e6f5e;padding:14px 16px;margin:20px 0;">
  Your account is now waiting for Dr. Mina Sherif’s approval.
</div>
<p>Once approved, you will be able to use your private patient portal, emotion journal, doctor channel, clinic feed, and appointment tools.</p>
<p><a href="{{portal_url}}" style="display:inline-block;background:#1f4e43;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;">Open Patient Portal</a></p>
<p>Thank you,<br />Dr. Mina Sherif’s Clinic</p>
```

## 2. Patient approved

Use for `profiles UPDATE` when `status` changes to `approved`.

Subject:

```text
Your Dr. Mina Sherif Patient Portal access is approved
```

Placeholders: `{{patient_name}}`, `{{portal_url}}`

Content:

```html
<p>Hello {{patient_name}},</p>
<p>Dr. Mina Sherif has approved your access to the Patient Portal.</p>
<div style="background:#eef6f1;border-left:4px solid #2e6f5e;padding:14px 16px;margin:20px 0;">
  Your private portal access is now active.
</div>
<p><a href="{{portal_url}}" style="display:inline-block;background:#1f4e43;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;">Open Patient Portal</a></p>
<p>Please remember that the private channel is for non-urgent messages only.</p>
<p>Warmly,<br />Dr. Mina Sherif</p>
```

## 3. Password reset — Supabase Auth

Use in Supabase → Authentication → Email Templates → Reset Password.

Subject:

```text
Reset your Dr. Mina Sherif Patient Portal password
```

Content:

```html
<h2 style="font-family:Georgia,serif;color:#1f4e43;">Reset your password</h2>
<p>Hello,</p>
<p>We received a request to create a new password for your Patient Portal account.</p>
<p><a href="{{ .ConfirmationURL }}" style="display:inline-block;background:#1f4e43;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;">Create New Password</a></p>
<p>This link expires according to the security settings of the portal. If you did not request this, you can safely ignore this email.</p>
<p>Dr. Mina Sherif’s Clinic</p>
```

## 4. New private message — patient receives doctor message

Use for `direct_messages INSERT` when `sender_role = doctor`.

Subject:

```text
You have a new private message from Dr. Mina Sherif
```

Placeholders: `{{patient_name}}`, `{{portal_url}}`

Content:

```html
<p>Hello {{patient_name}},</p>
<p>Dr. Mina Sherif sent you a new private message in your Patient Portal.</p>
<p><a href="{{portal_url}}" style="display:inline-block;background:#1f4e43;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;">Open Private Channel</a></p>
<p>Please do not use this channel for psychiatric emergencies.</p>
<p>Dr. Mina Sherif’s Clinic</p>
```

## 5. New private message — doctor receives patient message

Use for `direct_messages INSERT` when `sender_role = patient`.

Subject:

```text
A patient sent a new private portal message
```

Placeholders: `{{doctor_name}}`, `{{portal_url}}`

Content:

```html
<p>Hello {{doctor_name}},</p>
<p>A patient sent a new private message through the Patient Portal.</p>
<p><a href="{{portal_url}}/admin_panel" style="display:inline-block;background:#1f4e43;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;">Open Doctor Panel</a></p>
<p>Dr. Mina Sherif’s Patient Portal</p>
```

## 6. New appointment request — doctor receives notification

Use for `bookings INSERT`.

Subject:

```text
New patient appointment request
```

Placeholders: `{{doctor_name}}`, `{{portal_url}}`

Content:

```html
<p>Hello {{doctor_name}},</p>
<p>A patient has submitted a new appointment request.</p>
<p><a href="{{portal_url}}/admin_panel" style="display:inline-block;background:#1f4e43;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;">Review Appointment Request</a></p>
<p>Dr. Mina Sherif’s Patient Portal</p>
```

## 7. Appointment status updated — patient receives notification

Use for `bookings UPDATE` when the status changes.

Subject:

```text
Your appointment status was updated
```

Placeholders: `{{patient_name}}`, `{{booking_status}}`, `{{portal_url}}`

Content:

```html
<p>Hello {{patient_name}},</p>
<p>Your appointment status has been updated to:</p>
<div style="background:#eef6f1;border-left:4px solid #2e6f5e;padding:14px 16px;margin:20px 0;font-size:18px;font-weight:bold;">
  {{booking_status}}
</div>
<p><a href="{{portal_url}}/care" style="display:inline-block;background:#1f4e43;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;">View My Appointments</a></p>
<p>Dr. Mina Sherif’s Clinic</p>
```

## 8. New clinic broadcast — approved patients receive notification

Use for `clinic_feed INSERT`.

Subject:

```text
New clinic update from Dr. Mina Sherif
```

Placeholders: `{{patient_name}}`, `{{post_title}}`, `{{portal_url}}`

Content:

```html
<p>Hello {{patient_name}},</p>
<p>Dr. Mina Sherif has posted a new update in the Clinic Feed:</p>
<div style="background:#f7f5ef;border:1px solid #e2ddd2;border-radius:10px;padding:16px;margin:20px 0;">
  <strong style="font-size:17px;">{{post_title}}</strong>
</div>
<p><a href="{{portal_url}}/feed" style="display:inline-block;background:#1f4e43;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;">Open Clinic Feed</a></p>
<p>Dr. Mina Sherif’s Clinic</p>
```

## Email safety notes

- Keep emergency instructions in every clinical notification.
- Do not include emotion logs, diagnoses, medication details, or message content in email previews.
- Keep the full clinical content inside the authenticated portal.
- Replace every `{{...}}` backend placeholder with escaped text before inserting it into HTML.
- Keep Supabase Auth variables such as `{{ .ConfirmationURL }}` unchanged.
