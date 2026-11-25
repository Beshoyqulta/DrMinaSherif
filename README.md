# Dr. Mina Soliman — Patient Portal

Official web portal for patients of **Dr. Mina Soliman, MD**.

The Vercel site is the patient-facing web app. The `backend/` folder is a FastAPI service for production-only operations, using Supabase for authentication and data and designed for Render deployment.

## Included portal features
- **Private Patient Portal & Doctor Approval Gate** with offline-first storage and Supabase cloud sync
- **Centered Interactive 3-Ring Wheel of Emotions** (`540x540` SVG viewBox, zero clipping)
- **Log Emotion to Journal** workflow with SUDS intensity, somatic cues & triggers (patient entries only — zero demo data)
- **Direct WhatsApp Booking & Emergency Line**: `https://wa.me/201026281035`
- **Therapeutic Guided Meditation** & offline Web Audio soundscape mixer with Screen Wake Lock support
- **Personal Data Backup & Restore (.json)** in Care & Contact
- **Full-Screen Home Screen & Offline Support** (`manifest.json`, `sw.js`, dynamic `theme-color`)

## Production setup
1. Create a Supabase project and run [`supabase-setup.sql`](supabase-setup.sql) in the SQL Editor.
2. Configure Supabase Authentication for the Vercel site URL. Disable Confirm Email because this portal uses a welcome email followed by doctor approval; patients should not need to confirm their email before entering the pending-approval screen.
   Add the Netlify URL to the Supabase Redirect URLs as well; this is where password-reset links return.
3. Create the doctor's account in Supabase Auth using `minasherif@windowslive.com`, then run the promotion statement at the end of `supabase-setup.sql`. Set the password only in Supabase Auth; never commit it to the frontend or repository.
4. Deploy `backend/` to Render using [`render.yaml`](render.yaml). Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `ALLOWED_ORIGINS`. Never put the service-role key in Netlify or browser code.
5. Create a [Resend](https://resend.com) API key, verify the sender domain, and set `RESEND_API_KEY`, `FROM_EMAIL`, `APP_URL`, and `SUPABASE_WEBHOOK_SECRET` on Render.
6. In Supabase Database Webhooks, create POST webhooks to `https://YOUR-RENDER-SERVICE.onrender.com/webhooks/supabase` for `profiles` INSERT + UPDATE, `direct_messages` INSERT, `clinic_feed` INSERT, and `bookings` INSERT + UPDATE. A profile INSERT sends the welcome/pending-approval email; a profile UPDATE to approved sends the approval email. Add the `x-webhook-secret` header with the same value as `SUPABASE_WEBHOOK_SECRET`.
7. Check `/health`; API docs are available at `/docs`.
8. Update [`config.js`](config.js) with the Supabase URL, publishable/anon key, and Render backend URL, then redeploy Vercel. The browser only receives the Supabase publishable/anon key; service-role and Resend keys stay on Render.

The backend exposes `/api/me`, `/api/slots`, `/api/bookings`, `/api/messages/{patient_id}`, and `/api/feed`. Booking creation uses a database function and a unique active-booking index, so simultaneous requests cannot reserve the same slot. Email notifications are sent for approval, doctor messages, clinic broadcasts, and appointment status changes. If `RESEND_API_KEY` is absent, the service remains usable but skips email delivery.

The Vercel frontend uses browser routes for the main pages: `/patient`, `/meditation`, `/history`, `/feed`, `/care`, and `/admin_panel`. Doctor sessions are restricted to `/admin_panel`; patient navigation is hidden from the doctor view. Vercel serves these routes through `vercel.json` rewrites.

## Static hosting
1. Upload the contents of this folder onto **Netlify Drop**, **Cloudflare Pages**, **Vercel**, or **GitHub Pages**.
2. Share your HTTPS link with patients via WhatsApp.
3. Patients can open the link in their mobile or desktop browser and add **Dr. Mina Soliman** to their Home Screen for full-screen & offline access.
