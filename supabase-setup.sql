-- Dr. Mina Soliman portal schema. Run once in Supabase SQL Editor.
-- Never put SUPABASE_SERVICE_ROLE_KEY in Netlify or browser code.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text not null default '',
  phone text not null default '',
  role text not null default 'patient' check (role in ('patient','doctor')),
  status text not null default 'pending' check (status in ('pending','approved','rejected','revoked')),
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_user() returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email, full_name, phone) values (new.id, new.email, coalesce(new.raw_user_meta_data->>'full_name',''), coalesce(new.raw_user_meta_data->>'phone',''));
  return new;
end; $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users for each row execute procedure public.handle_new_user();

create table if not exists public.emotion_logs (
  id text primary key, user_id uuid not null references public.profiles(id) on delete cascade,
  logged_at bigint not null, core text not null, secondary text not null, tertiary text not null,
  color text, intensity integer, co_emotions jsonb not null default '[]', somatic jsonb not null default '[]',
  triggers jsonb not null default '[]', note text not null default '', created_at timestamptz not null default now()
);
create table if not exists public.patient_state (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  meditation_minutes integer not null default 0, care_plan jsonb not null default '{}', updated_at timestamptz not null default now()
);

create table if not exists public.availability_slots (
  id uuid primary key default gen_random_uuid(), starts_at timestamptz not null, ends_at timestamptz not null,
  label text, is_open boolean not null default true, created_at timestamptz not null default now(),
  check (ends_at > starts_at), unique (starts_at, ends_at)
);

create table if not exists public.bookings (
  id uuid primary key default gen_random_uuid(), slot_id uuid references public.availability_slots(id),
  patient_id uuid not null references public.profiles(id) on delete cascade, patient_name text not null default '',
  patient_email text not null default '', patient_phone text not null default '', session_type text not null,
  session_format text not null, preferred_date text not null default '', preferred_time text not null default '',
  patient_note text not null default '', status text not null default 'pending' check (status in ('pending','confirmed','rescheduled','completed','cancelled')),
  confirmed_date text not null default '', confirmed_time text not null default '', meeting_link text not null default '',
  doctor_note text not null default '', created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create unique index if not exists one_active_booking_per_slot on public.bookings(slot_id) where status in ('pending','confirmed','rescheduled');
create unique index if not exists one_active_booking_per_time on public.bookings(preferred_date, preferred_time) where slot_id is null and status in ('pending','confirmed','rescheduled');

create or replace function public.book_available_slot(p_slot_id uuid, p_patient_id uuid, p_session_type text, p_session_format text, p_patient_note text)
returns public.bookings language plpgsql security definer set search_path = public as $$
declare s public.availability_slots; b public.bookings;
begin
  select * into s from public.availability_slots where id = p_slot_id and is_open = true for update;
  if not found then raise exception 'slot_unavailable'; end if;
  insert into public.bookings (slot_id, patient_id, patient_name, patient_email, patient_phone, session_type, session_format, preferred_date, preferred_time, patient_note)
    select p_slot_id, p_patient_id, full_name, email, phone, p_session_type, p_session_format, to_char(s.starts_at at time zone 'Africa/Cairo','YYYY-MM-DD'), to_char(s.starts_at at time zone 'Africa/Cairo','HH24:MI'), coalesce(p_patient_note,'')
    from public.profiles where id = p_patient_id and status = 'approved' returning * into b;
  if not found then raise exception 'patient_not_approved'; end if;
  return b;
exception when unique_violation then raise exception 'slot_unavailable';
end; $$;

create or replace function public.protect_patient_booking_update() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if not public.is_doctor() and auth.uid() = old.patient_id then
    if new.patient_id <> old.patient_id or new.slot_id is distinct from old.slot_id or new.status <> 'cancelled'
       or new.session_type <> old.session_type or new.session_format <> old.session_format
       or new.confirmed_date <> old.confirmed_date or new.confirmed_time <> old.confirmed_time
       or new.meeting_link <> old.meeting_link or new.doctor_note <> old.doctor_note then
      raise exception 'patients may only cancel their own booking';
    end if;
  end if;
  return new;
end; $$;
drop trigger if exists protect_patient_booking_update on public.bookings;
create trigger protect_patient_booking_update before update on public.bookings for each row execute procedure public.protect_patient_booking_update();

create table if not exists public.direct_messages (
  id uuid primary key default gen_random_uuid(), patient_id uuid not null references public.profiles(id) on delete cascade,
  sender_id uuid not null references public.profiles(id), sender_role text not null check (sender_role in ('patient','doctor')),
  sender_name text not null default '', body text not null, read_by_doctor boolean not null default false,
  read_by_patient boolean not null default false, created_at timestamptz not null default now()
);
create table if not exists public.clinic_feed (
  id uuid primary key default gen_random_uuid(), author_id uuid not null references public.profiles(id), author_name text not null default '',
  title text not null, category text not null default 'Clinic Announcement', body text not null, resource_url text not null default '',
  resource_label text not null default '', pinned boolean not null default false, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create or replace function public.is_doctor() returns boolean language sql stable security definer set search_path = public as $$ select exists(select 1 from public.profiles where id = auth.uid() and role='doctor' and status='approved'); $$;
create or replace function public.is_approved() returns boolean language sql stable security definer set search_path = public as $$ select exists(select 1 from public.profiles where id = auth.uid() and status='approved'); $$;

alter table public.profiles enable row level security;
alter table public.emotion_logs enable row level security;
alter table public.patient_state enable row level security;
alter table public.availability_slots enable row level security;
alter table public.bookings enable row level security;
alter table public.direct_messages enable row level security;
alter table public.clinic_feed enable row level security;

drop policy if exists profiles_self_or_doctor on public.profiles;
create policy profiles_self_or_doctor on public.profiles for select using (id=auth.uid() or public.is_doctor());
drop policy if exists doctor_updates_profiles on public.profiles;
create policy doctor_updates_profiles on public.profiles for update using (public.is_doctor()) with check (public.is_doctor());
drop policy if exists logs_owner_or_doctor on public.emotion_logs;
create policy logs_owner_or_doctor on public.emotion_logs for all using (user_id=auth.uid() or public.is_doctor()) with check (user_id=auth.uid() or public.is_doctor());
drop policy if exists state_owner_or_doctor on public.patient_state;
create policy state_owner_or_doctor on public.patient_state for all using (user_id=auth.uid() or public.is_doctor()) with check (user_id=auth.uid() or public.is_doctor());
drop policy if exists slots_approved_read on public.availability_slots;
create policy slots_approved_read on public.availability_slots for select using (public.is_approved());
drop policy if exists slots_doctor_write on public.availability_slots;
create policy slots_doctor_write on public.availability_slots for all using (public.is_doctor()) with check (public.is_doctor());
drop policy if exists bookings_patient_or_doctor on public.bookings;
create policy bookings_patient_or_doctor on public.bookings for select using (patient_id=auth.uid() or public.is_doctor());
drop policy if exists bookings_patient_insert on public.bookings;
create policy bookings_patient_insert on public.bookings for insert with check (patient_id=auth.uid() and public.is_approved());
drop policy if exists bookings_doctor_update on public.bookings;
create policy bookings_doctor_update on public.bookings for update using (public.is_doctor()) with check (public.is_doctor());
drop policy if exists bookings_patient_cancel on public.bookings;
create policy bookings_patient_cancel on public.bookings for update using (patient_id=auth.uid()) with check (patient_id=auth.uid() and status='cancelled');
drop policy if exists messages_participants on public.direct_messages;
create policy messages_participants on public.direct_messages for all using (patient_id=auth.uid() or public.is_doctor()) with check (patient_id=auth.uid() or public.is_doctor());
drop policy if exists feed_approved_read on public.clinic_feed;
create policy feed_approved_read on public.clinic_feed for select using (public.is_approved());
drop policy if exists feed_doctor_write on public.clinic_feed;
create policy feed_doctor_write on public.clinic_feed for all using (public.is_doctor()) with check (public.is_doctor());

-- After the first sign-up, promote the doctor's auth UUID explicitly:
-- update public.profiles set role='doctor', status='approved' where email='doctor@drminasoliman.com';
