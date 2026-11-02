-- Streckenatlas: einmalig im Supabase "SQL Editor" ausführen

-- Profile mit Rolle (neue Konten warten auf Freischaltung)
create table public.profiles (
  id uuid primary key references auth.users on delete cascade,
  email text,
  name text,
  role text not null default 'wartend' check (role in ('wartend','mitarbeiter','admin')),
  created_at timestamptz not null default now()
);

-- Objekte auf der Karte
create table public.markers (
  id uuid primary key default gen_random_uuid(),
  created_by uuid not null default auth.uid() references public.profiles(id) on delete cascade,
  lat double precision not null,
  lng double precision not null,
  typ text not null,
  titel text not null check (char_length(titel) between 1 and 80),
  notiz text check (char_length(notiz) <= 1000),
  created_at timestamptz not null default now()
);

-- Hilfsfunktionen für die Rechte
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from profiles where id = auth.uid() and role = 'admin');
$$;

create or replace function public.is_member() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from profiles where id = auth.uid() and role in ('mitarbeiter','admin'));
$$;

-- Profil automatisch anlegen, wenn sich jemand registriert
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, email, name)
  values (new.id, new.email, coalesce(nullif(new.raw_user_meta_data->>'name',''), split_part(new.email,'@',1)));
  return new;
end; $$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Zugriffsregeln
alter table public.profiles enable row level security;
alter table public.markers  enable row level security;

create policy "Profile lesen"      on public.profiles for select to authenticated using (id = auth.uid() or is_member());
create policy "Rollen nur Admin"   on public.profiles for update to authenticated using (is_admin()) with check (is_admin());

create policy "Objekte lesen"      on public.markers for select to authenticated using (is_member());
create policy "Objekte anlegen"    on public.markers for insert to authenticated with check (is_member() and created_by = auth.uid());
create policy "Objekte entfernen"  on public.markers for delete to authenticated using (is_admin());

-- Live-Aktualisierung, wenn Kollegen etwas eintragen
alter publication supabase_realtime add table public.markers;

-- NACH deiner eigenen Registrierung in der App einmal ausführen (E-Mail anpassen):
-- update public.profiles set role = 'admin' where email = 'deine@mail.de';
