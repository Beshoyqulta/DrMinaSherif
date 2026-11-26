from __future__ import annotations

import asyncio
import os
import logging
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail
from supabase import Client, create_client
from app.email_templates import (
    appointment_updated,
    approved,
    clinic_broadcast,
    doctor_message,
    doctor_new_appointment,
    doctor_appointment_cancelled,
    doctor_new_message,
    doctor_new_signup,
    appointment_reminder,
    patient_login,
    welcome,
)


SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "*").split(",") if x.strip()]
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "")
FROM_NAME = os.getenv("FROM_NAME", "Dr. Mina Sherif")
DEFAULT_APP_URL = "https://drminasoliman-website.vercel.app"
APP_URL = os.getenv("APP_URL", DEFAULT_APP_URL).strip().rstrip("/") or DEFAULT_APP_URL
WEBHOOK_SECRET = os.getenv("SUPABASE_WEBHOOK_SECRET", "")

logger = logging.getLogger("dr-mina-portal")

admin_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
auth_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
app = FastAPI(title="Dr. Mina Soliman Patient Portal API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
CAIRO_TZ = ZoneInfo("Africa/Cairo")
reminder_task: asyncio.Task | None = None


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    try:
        auth_user = auth_client.auth.get_user(authorization.split(" ", 1)[1].strip()).user
        if not auth_user:
            raise ValueError("No user")
        profile = admin_client.table("profiles").select("*").eq("id", str(auth_user.id)).single().execute().data
        if not profile:
            raise ValueError("No profile")
        return {"auth": auth_user, "profile": profile}
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc


def approved_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user["profile"].get("status") != "approved":
        raise HTTPException(status_code=403, detail="Portal access is awaiting doctor approval")
    return user


def doctor_only(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user["profile"].get("role") != "doctor" or user["profile"].get("status") != "approved":
        raise HTTPException(status_code=403, detail="Doctor access required")
    return user


class SlotIn(BaseModel):
    starts_at: datetime
    ends_at: datetime
    label: str | None = Field(default=None, max_length=120)


class BookingIn(BaseModel):
    slot_id: UUID
    session_type: str = Field(min_length=1, max_length=120)
    session_format: str = Field(min_length=1, max_length=40)
    patient_note: str = Field(default="", max_length=2000)


class BookingUpdate(BaseModel):
    status: str = Field(pattern="^(confirmed|rescheduled|completed|cancelled)$")
    doctor_note: str = Field(default="", max_length=2000)
    meeting_link: str = Field(default="", max_length=500)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class BroadcastIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    category: str = Field(default="Clinic Announcement", max_length=80)
    body: str = Field(min_length=1, max_length=6000)
    resource_url: str = Field(default="", max_length=500)
    resource_label: str = Field(default="", max_length=80)
    pinned: bool = False


def send_email(to: str, subject: str, html: str) -> bool:
    if not SENDGRID_API_KEY or not FROM_EMAIL or not to:
        logger.warning("Email skipped: SendGrid API key, sender, or recipient is missing")
        return False
    logger.info("Sending email subject=%r recipient=%s from=%s", subject, to, FROM_EMAIL)
    sender = Email(FROM_EMAIL.strip(), FROM_NAME.strip() or None)
    message = Mail(from_email=sender, to_emails=to, subject=subject, html_content=html)
    try:
        response = SendGridAPIClient(SENDGRID_API_KEY).send(message)
        if response.status_code >= 400:
            raise RuntimeError(f"SendGrid rejected email with HTTP {response.status_code}: {response.body}")
        logger.info("SendGrid accepted message recipient=%s status=%s", to, response.status_code)
        return True
    except Exception as exc:
        provider_error = str(getattr(exc, "body", "") or "")
        logger.exception(
            "SendGrid rejected message subject=%r recipient=%s provider_response=%s",
            subject,
            to,
            provider_error,
        )
        # Email delivery must not make a Supabase webhook fail. The database
        # change is already committed; the failure is recorded in Render logs
        # for retry/diagnosis without causing webhook retry storms.
        return False
 

def portal_link(path: str = "") -> str:
    return f"{APP_URL}/{path.lstrip('/')}"


def profile_for(user_id: str | None) -> dict[str, Any] | None:
    if not user_id:
        return None
    result = admin_client.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
    return result.data if result.data else None


def doctor_email_recipients() -> list[dict[str, Any]]:
    """Return doctor-account email recipients from Supabase profiles."""
    result = (
        admin_client.table("profiles")
        .select("email,full_name,role,status")
        .eq("role", "doctor")
        .execute()
    )
    doctors = [doctor for doctor in (result.data or []) if str(doctor.get("email") or "").strip()]
    if not doctors:
        logger.warning("No doctor email recipient found in public.profiles (role=doctor)")
    return doctors


def notify_profile_approval(record: dict[str, Any], old_record: dict[str, Any] | None) -> None:
    if record.get("status") == "approved" and (not old_record or old_record.get("status") != "approved"):
        subject, html = approved(record.get("full_name", ""), portal_link())
        send_email(record.get("email", ""), subject, html)


def notify_profile_created(record: dict[str, Any]) -> None:
    subject, html = welcome(record.get("full_name", ""), portal_link())
    send_email(record.get("email", ""), subject, html)


def notify_new_message(record: dict[str, Any]) -> None:
    if record.get("sender_role") == "doctor":
        patient = profile_for(record.get("patient_id"))
        if patient:
            name = patient.get("full_name") or "there"
            send_email(patient.get("email", ""), "You have a new message from Dr. Mina Soliman", f"<p>Hello {escape(name)},</p><p>Dr. Mina Soliman sent you a new private portal message.</p><p><a href=\"{portal_link()}\">Open your message channel</a></p>")
    else:
        for doctor in doctor_email_recipients():
            send_email(doctor.get("email", ""), "A patient sent you a new private message", f"<p>Hello {escape(doctor.get('full_name') or 'Doctor')},</p><p>A patient sent a new private portal message.</p><p><a href=\"{portal_link()}\">Open the doctor portal</a></p>")


def notify_new_broadcast(record: dict[str, Any]) -> None:
    patients = admin_client.table("profiles").select("email,full_name").eq("role", "patient").eq("status", "approved").execute().data or []
    subject = record.get("title") or "New clinic message from Dr. Mina Soliman"
    for patient in patients:
        name = patient.get("full_name") or "there"
        send_email(patient.get("email", ""), subject, f"<p>Hello {escape(name)},</p><p>Dr. Mina Soliman posted a new clinic update: <strong>{escape(subject)}</strong></p><p><a href=\"{portal_link()}\">Open the clinic feed</a></p>")


def notify_booking_update(record: dict[str, Any], old_record: dict[str, Any] | None, event: str) -> None:
    if event == "INSERT":
        for doctor in doctor_email_recipients():
            send_email(doctor.get("email", ""), "A patient requested an appointment", f"<p>Hello {escape(doctor.get('full_name') or 'Doctor')},</p><p>A patient submitted a new appointment request.</p><p><a href=\"{portal_link()}\">Open the doctor portal</a></p>")
        return
    if old_record and record.get("status") == old_record.get("status"):
        return
    patient = profile_for(record.get("patient_id"))
    if not patient:
        return
    status_text = record.get("status", "updated")
    send_email(patient.get("email", ""), "Your appointment was updated", f"<p>Hello {escape(patient.get('full_name') or 'there')},</p><p>Your appointment status is now <strong>{escape(status_text)}</strong>.</p><p><a href=\"{portal_link()}\">Open your appointments</a></p>")


def templated_profile_created(record: dict[str, Any]) -> None:
    subject, html = welcome(record.get("full_name", ""), portal_link())
    send_email(record.get("email", ""), subject, html)
    for doctor in doctor_email_recipients():
        subject, html = doctor_new_signup(
            record.get("full_name", ""),
            record.get("email", ""),
            portal_link(),
        )
        send_email(doctor.get("email", ""), subject, html)


def templated_profile_approval(record: dict[str, Any], old_record: dict[str, Any] | None) -> None:
    if record.get("status") == "approved" and (not old_record or old_record.get("status") != "approved"):
        subject, html = approved(record.get("full_name", ""), portal_link())
        send_email(record.get("email", ""), subject, html)


def templated_new_message(record: dict[str, Any]) -> None:
    if record.get("sender_role") == "doctor":
        patient = profile_for(record.get("patient_id"))
        if patient:
            subject, html = doctor_message(patient.get("full_name", ""), portal_link())
            send_email(patient.get("email", ""), subject, html)
        return
    patient = profile_for(record.get("sender_id"))
    patient_name = (patient or {}).get("full_name") or record.get("sender_name", "")
    patient_email = (patient or {}).get("email", "")
    for doctor in doctor_email_recipients():
        subject, html = doctor_new_message(
            doctor.get("full_name", ""),
            patient_name,
            patient_email,
            portal_link(),
        )
        send_email(doctor.get("email", ""), subject, html)


def templated_broadcast(record: dict[str, Any]) -> None:
    patients = admin_client.table("profiles").select("email,full_name").eq("role", "patient").eq("status", "approved").execute().data or []
    for patient in patients:
        subject, html = clinic_broadcast(patient.get("full_name", ""), record.get("title", ""), portal_link())
        send_email(patient.get("email", ""), subject, html)


def templated_booking_update(record: dict[str, Any], old_record: dict[str, Any] | None, event: str) -> None:
    if event == "INSERT":
        for doctor in doctor_email_recipients():
            subject, html = doctor_new_appointment(
                doctor.get("full_name", ""),
                record.get("patient_name", ""),
                record.get("patient_email", ""),
                record.get("session_type", ""),
                record.get("preferred_date", ""),
                record.get("preferred_time", ""),
                portal_link(),
            )
            send_email(doctor.get("email", ""), subject, html)
        return
    if old_record and all(record.get(field) == old_record.get(field) for field in ("status", "confirmed_date", "confirmed_time")):
        return
    patient = profile_for(record.get("patient_id"))
    if record.get("status") == "cancelled":
        for doctor in doctor_email_recipients():
            subject, html = doctor_appointment_cancelled(
                doctor.get("full_name", ""),
                (patient or {}).get("full_name", record.get("patient_name", "")),
                (patient or {}).get("email", record.get("patient_email", "")),
                record.get("session_type", ""),
                record.get("confirmed_date") or record.get("preferred_date", ""),
                record.get("confirmed_time") or record.get("preferred_time", ""),
                portal_link(),
            )
            send_email(doctor.get("email", ""), subject, html)
        return
    if patient:
        subject, html = appointment_updated(
            patient.get("full_name", ""),
            record.get("status", "updated"),
            record.get("confirmed_date", ""),
            record.get("confirmed_time", ""),
            portal_link(),
        )
        send_email(patient.get("email", ""), subject, html)


def notify_doctors_of_patient_login(patient: dict[str, Any]) -> None:
    for doctor in doctor_email_recipients():
        subject, html = patient_login(patient.get("full_name", ""), patient.get("email", ""), portal_link())
        send_email(doctor.get("email", ""), subject, html)


def booking_start_time(record: dict[str, Any]) -> datetime | None:
    booking_date = str(record.get("confirmed_date") or "").strip()
    booking_time = str(record.get("confirmed_time") or "").strip()
    if not booking_date or not booking_time:
        return None
    for value in (f"{booking_date} {booking_time}", f"{booking_date}T{booking_time}"):
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M %p", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%I:%M %p"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=CAIRO_TZ)
            except ValueError:
                continue
    logger.warning("Could not parse confirmed booking date/time: date=%r time=%r", booking_date, booking_time)
    return None


def send_due_appointment_reminders() -> None:
    now = datetime.now(CAIRO_TZ)
    try:
        result = (
            admin_client.table("bookings")
            .select("*")
            .eq("status", "confirmed")
            .is_("reminder_sent_at", "null")
            .execute()
        )
        for booking in result.data or []:
            start = booking_start_time(booking)
            if not start:
                continue
            seconds_until_start = (start - now).total_seconds()
            if not 0 < seconds_until_start <= 30 * 60:
                continue
            patient = profile_for(booking.get("patient_id"))
            if not patient or not patient.get("email"):
                continue
            subject, html = appointment_reminder(
                patient.get("full_name", ""),
                booking.get("confirmed_date", ""),
                booking.get("confirmed_time", ""),
                portal_link(),
            )
            if send_email(patient["email"], subject, html):
                admin_client.table("bookings").update({"reminder_sent_at": datetime.now(timezone.utc).isoformat()}).eq("id", str(booking["id"])).is_("reminder_sent_at", "null").execute()
                logger.info("Appointment reminder sent booking=%s recipient=%s", booking.get("id"), patient["email"])
    except Exception:
        logger.exception("Appointment reminder scan failed")


async def appointment_reminder_loop() -> None:
    while True:
        await asyncio.to_thread(send_due_appointment_reminders)
        await asyncio.sleep(60)


@app.on_event("startup")
async def start_appointment_reminder_loop() -> None:
    global reminder_task
    reminder_task = asyncio.create_task(appointment_reminder_loop())


@app.on_event("shutdown")
async def stop_appointment_reminder_loop() -> None:
    if reminder_task:
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "dr-mina-portal-api", "health": "/health"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "dr-mina-portal-api"}


@app.post("/webhooks/supabase")
def supabase_webhook(payload: dict[str, Any], x_webhook_secret: str | None = Header(default=None)) -> dict[str, bool]:
    logger.info("Supabase webhook received type=%s table=%s", payload.get("type"), payload.get("table"))
    if WEBHOOK_SECRET and x_webhook_secret != WEBHOOK_SECRET:
        logger.warning("Supabase webhook rejected: invalid secret")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    table = payload.get("table")
    record = payload.get("record") or {}
    old_record = payload.get("old_record") or {}
    event = payload.get("type") or payload.get("eventType")
    if table == "profiles" and event == "INSERT":
        templated_profile_created(record)
    elif table == "profiles" and event == "UPDATE":
        templated_profile_approval(record, old_record)
    elif table == "direct_messages" and event == "INSERT":
        templated_new_message(record)
    elif table == "clinic_feed" and event == "INSERT":
        templated_broadcast(record)
    elif table == "bookings" and event in {"INSERT", "UPDATE"}:
        templated_booking_update(record, old_record, event)
    return {"ok": True}


@app.get("/api/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return user["profile"]


@app.post("/api/login-notification")
def login_notification(user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    profile = user["profile"]
    if profile.get("role") == "patient":
        notify_doctors_of_patient_login(profile)
    return {"ok": True}


@app.get("/api/slots")
def list_slots(from_date: date | None = Query(default=None), to_date: date | None = Query(default=None), _user: dict[str, Any] = Depends(approved_user)) -> list[dict[str, Any]]:
    query = admin_client.table("availability_slots").select("*, bookings(id, status)").eq("is_open", True)
    if from_date:
        query = query.gte("starts_at", f"{from_date.isoformat()}T00:00:00+00:00")
    if to_date:
        query = query.lt("starts_at", f"{to_date.isoformat()}T23:59:59+00:00")
    rows = query.order("starts_at").execute().data or []
    return [r for r in rows if not any(b.get("status") in {"pending", "confirmed", "rescheduled"} for b in (r.get("bookings") or []))]


@app.post("/api/slots", status_code=201)
def create_slot(payload: SlotIn, _user: dict[str, Any] = Depends(doctor_only)) -> dict[str, Any]:
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="Slot end must be after slot start")
    try:
        return admin_client.table("availability_slots").insert(payload.model_dump(mode="json")).execute().data[0]
    except Exception as exc:
        raise HTTPException(status_code=409, detail="That availability slot already exists") from exc


@app.delete("/api/slots/{slot_id}")
def close_slot(slot_id: UUID, _user: dict[str, Any] = Depends(doctor_only)) -> dict[str, bool]:
    admin_client.table("availability_slots").update({"is_open": False}).eq("id", str(slot_id)).execute()
    return {"ok": True}


@app.post("/api/bookings", status_code=201)
def create_booking(payload: BookingIn, user: dict[str, Any] = Depends(approved_user)) -> dict[str, Any]:
    try:
        result = admin_client.rpc("book_available_slot", {
            "p_slot_id": str(payload.slot_id), "p_patient_id": str(user["profile"]["id"]),
            "p_session_type": payload.session_type, "p_session_format": payload.session_format,
            "p_patient_note": payload.patient_note,
        }).execute()
        return result.data
    except Exception as exc:
        raise HTTPException(status_code=409, detail="That slot is no longer available") from exc


@app.get("/api/bookings")
def list_bookings(user: dict[str, Any] = Depends(approved_user)) -> list[dict[str, Any]]:
    query = admin_client.table("bookings").select("*, availability_slots(*)").order("created_at", desc=True)
    if user["profile"].get("role") != "doctor":
        query = query.eq("patient_id", str(user["profile"]["id"]))
    return query.execute().data or []


@app.patch("/api/bookings/{booking_id}")
def update_booking(booking_id: UUID, payload: BookingUpdate, _user: dict[str, Any] = Depends(doctor_only)) -> dict[str, Any]:
    result = admin_client.table("bookings").update(payload.model_dump()).eq("id", str(booking_id)).execute().data or []
    if not result:
        raise HTTPException(status_code=404, detail="Booking not found")
    return result[0]


@app.get("/api/messages/{patient_id}")
def list_messages(patient_id: UUID, user: dict[str, Any] = Depends(approved_user)) -> list[dict[str, Any]]:
    is_doctor = user["profile"].get("role") == "doctor"
    if not is_doctor and str(user["profile"]["id"]) != str(patient_id):
        raise HTTPException(status_code=403, detail="This channel is private")
    return admin_client.table("direct_messages").select("*").eq("patient_id", str(patient_id)).order("created_at").execute().data or []


@app.post("/api/messages/{patient_id}", status_code=201)
def send_message(patient_id: UUID, payload: MessageIn, user: dict[str, Any] = Depends(approved_user)) -> dict[str, Any]:
    is_doctor = user["profile"].get("role") == "doctor"
    if not is_doctor and str(user["profile"]["id"]) != str(patient_id):
        raise HTTPException(status_code=403, detail="This channel is private")
    row = {"patient_id": str(patient_id), "sender_id": str(user["profile"]["id"]), "sender_role": "doctor" if is_doctor else "patient", "sender_name": user["profile"].get("full_name") or user["profile"].get("email"), "body": payload.body.strip(), "read_by_doctor": is_doctor, "read_by_patient": not is_doctor}
    return admin_client.table("direct_messages").insert(row).execute().data[0]


@app.get("/api/feed")
def feed(_user: dict[str, Any] = Depends(approved_user)) -> list[dict[str, Any]]:
    return admin_client.table("clinic_feed").select("*").order("pinned", desc=True).order("created_at", desc=True).execute().data or []


@app.post("/api/feed", status_code=201)
def publish_feed(payload: BroadcastIn, user: dict[str, Any] = Depends(doctor_only)) -> dict[str, Any]:
    row = payload.model_dump()
    row.update({"author_id": str(user["profile"]["id"]), "author_name": user["profile"].get("full_name") or "Dr. Mina Soliman, MD"})
    return admin_client.table("clinic_feed").insert(row).execute().data[0]

