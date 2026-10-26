-- Recall Database Schema
-- Run this in your Supabase SQL editor to set up the database

create extension if not exists "pgcrypto";

create table if not exists entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  title text not null,
  media_type text not null check (media_type in (
    'book', 'film', 'tv_series', 'tv_episode', 'podcast',
    'album', 'song', 'youtube', 'article', 'live_event', 'other'
  )),
  thumbnail_url text,
  note text check (char_length(note) <= 280),
  rating integer check (rating >= 1 and rating <= 5),
  logged_at timestamp with time zone default now(),
  source_url text,
  source_api text check (source_api in ('openlibrary', 'tmdb', 'spotify', 'youtube', 'manual')),
  source_api_id text,
  author_or_creator text,
  year integer,
  created_at timestamp with time zone default now()
);

create index if not exists idx_entries_user on entries(user_id);
create index if not exists idx_entries_logged on entries(user_id, logged_at desc);
create index if not exists idx_entries_search on entries using gin(
  to_tsvector('english', title || ' ' || coalesce(note, ''))
);
create index if not exists idx_entries_media_type on entries(user_id, media_type);

alter table entries enable row level security;

create policy "Users can view own entries" on entries
  for select using (auth.uid() = user_id);

create policy "Users can insert own entries" on entries
  for insert with check (auth.uid() = user_id);

create policy "Users can update own entries" on entries
  for update using (auth.uid() = user_id);

create policy "Users can delete own entries" on entries
  for delete using (auth.uid() = user_id);

-- User settings (API keys, preferences, OAuth tokens)
create table if not exists user_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  tmdb_api_key text,
  spotify_access_token text,
  spotify_refresh_token text,
  spotify_token_expires_at timestamp with time zone,
  youtube_access_token text,
  youtube_refresh_token text,
  youtube_token_expires_at timestamp with time zone,
  updated_at timestamp with time zone default now()
);

alter table user_settings enable row level security;

create policy "Users can view own settings" on user_settings
  for select using (auth.uid() = user_id);

create policy "Users can insert own settings" on user_settings
  for insert with check (auth.uid() = user_id);

create policy "Users can update own settings" on user_settings
  for update using (auth.uid() = user_id);
