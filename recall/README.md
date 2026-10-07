# Recall — Your Personal Media Memory

Log everything you consume — books, films, TV shows, podcasts, music, YouTube videos, articles, live events — in under 5 seconds, then search and revisit your history later.

## Features

- **Quick Log** — Spotlight-style search bar that auto-suggests from TMDB (films/TV) and Open Library (books). One tap to log.
- **URL Paste** — Paste a YouTube or Spotify link and metadata is auto-extracted.
- **Timeline** — Reverse-chronological feed of everything you've logged, filterable by type and date.
- **Search** — Full-text search across titles and notes.
- **Stats Dashboard** — Total entries, breakdown by type, monthly activity chart, streaks, and "on this day" memories.
- **PWA** — Installable on mobile without an app store.

## Tech Stack

- **Framework:** Next.js (App Router) with TypeScript
- **Styling:** Tailwind CSS with custom dark theme
- **Database & Auth:** Supabase (PostgreSQL + Auth with email/password and Google OAuth)
- **Media APIs:** TMDB (films/TV), Open Library (books)
- **Charts:** Recharts
- **Icons:** Lucide React
- **Deployment:** Vercel

## Getting Started

### 1. Clone and install

```bash
cd recall
npm install
```

### 2. Set up Supabase

1. Create a new project at [supabase.com](https://supabase.com)
2. Run the SQL in `supabase/schema.sql` in your Supabase SQL editor
3. Enable email/password auth in Authentication > Providers
4. (Optional) Enable Google OAuth in Authentication > Providers > Google

### 3. Set up TMDB

1. Sign up at [themoviedb.org](https://www.themoviedb.org/) and get an API key
2. Copy it to your environment variables

### 4. Configure environment

```bash
cp .env.local.example .env.local
```

Fill in:
- `NEXT_PUBLIC_SUPABASE_URL` — Your Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Your Supabase anon key
- `TMDB_API_KEY` — Your TMDB API key

### 5. Run development server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Project Structure

```
recall/
├── public/
│   └── manifest.json          # PWA manifest
├── supabase/
│   └── schema.sql             # Database schema with RLS
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── entries/       # CRUD for log entries
│   │   │   ├── search/        # Media API search + URL detection
│   │   │   └── stats/         # Stats aggregation
│   │   ├── auth/callback/     # OAuth callback handler
│   │   ├── login/             # Login page
│   │   ├── signup/            # Signup page
│   │   ├── search/            # Search page
│   │   ├── stats/             # Stats dashboard
│   │   ├── layout.tsx         # Root layout
│   │   └── page.tsx           # Home (timeline)
│   ├── components/
│   │   ├── app-shell.tsx      # Navigation shell
│   │   ├── quick-log.tsx      # Quick log search bar
│   │   ├── timeline.tsx       # Timeline feed
│   │   ├── search-view.tsx    # Search page content
│   │   ├── stats-view.tsx     # Stats dashboard content
│   │   ├── media-type-badge.tsx
│   │   └── star-rating.tsx
│   └── lib/
│       ├── supabase/          # Supabase client configs
│       └── types.ts           # TypeScript types
└── .env.local.example
```

## Design

- Dark mode with warm background (#1a1a2e)
- Lora serif for headings, DM Sans for body
- Colour-coded media types: Books (amber), Films (red), TV (indigo), Podcasts (green), Music (violet), YouTube (coral), Articles (teal), Live Events (gold)
- Smooth fade-in animations on entry creation
