-- Run this in Supabase > SQL Editor to create the logging tables.
-- The 'appointments' table is TASK-SPECIFIC (example) — adjust once you
-- know the real domain.

create table if not exists calls (
    id           bigint generated always as identity primary key,
    call_id      text,
    phone_number text,
    summary      text,
    transcript   text,
    ended_reason text,
    created_at   timestamptz default now()
);

create table if not exists call_events (
    id         bigint generated always as identity primary key,
    event_type text,
    payload    jsonb,
    created_at timestamptz default now()
);

-- TASK-SPECIFIC example table --------------------------------------------
create table if not exists appointments (
    id           bigint generated always as identity primary key,
    patient_name text,
    date         text,
    time         text,
    created_at   timestamptz default now()
);
