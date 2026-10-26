-- Run only in Supabase after the app creates its tables.
-- The SQLAlchemy backend uses its privileged database role; no client-side Data API access is needed.
ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inquiries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.patients, public.appointments, public.inquiries FROM anon, authenticated;
