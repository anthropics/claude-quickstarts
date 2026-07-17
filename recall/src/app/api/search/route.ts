import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import type { SearchResult, MediaType } from "@/lib/types";

interface TMDBResult {
  id: number;
  media_type: string;
  title?: string;
  name?: string;
  poster_path: string | null;
  release_date?: string;
  first_air_date?: string;
}

interface OpenLibraryDoc {
  key: string;
  title: string;
  author_name?: string[];
  first_publish_year?: number;
  cover_edition_key?: string;
}

interface OpenLibraryResponse {
  docs: OpenLibraryDoc[];
}

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q");

  if (!q || q.trim().length === 0) {
    return NextResponse.json(
      { error: "Query parameter q is required" },
      { status: 400 }
    );
  }

  // Get TMDB key from user settings (falls back to env var)
  let tmdbApiKey = process.env.TMDB_API_KEY || "";
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    const { data: settings } = await supabase
      .from("user_settings")
      .select("tmdb_api_key")
      .eq("user_id", user.id)
      .single();

    if (settings?.tmdb_api_key) {
      tmdbApiKey = settings.tmdb_api_key;
    }
  }

  const encodedQuery = encodeURIComponent(q);

  const [tmdbResults, openLibraryResults] = await Promise.allSettled([
    searchTMDB(encodedQuery, tmdbApiKey),
    searchOpenLibrary(encodedQuery),
  ]);

  const results: SearchResult[] = [];

  if (tmdbResults.status === "fulfilled") {
    results.push(...tmdbResults.value);
  }

  if (openLibraryResults.status === "fulfilled") {
    results.push(...openLibraryResults.value);
  }

  return NextResponse.json(results);
}

async function searchTMDB(encodedQuery: string, apiKey: string): Promise<SearchResult[]> {
  if (!apiKey) return [];

  const response = await fetch(
    `https://api.themoviedb.org/3/search/multi?query=${encodedQuery}&api_key=${apiKey}`,
    { next: { revalidate: 3600 } }
  );

  if (!response.ok) return [];

  const data = await response.json();
  const results: TMDBResult[] = data.results ?? [];

  return results
    .filter(
      (item) => item.media_type === "movie" || item.media_type === "tv"
    )
    .slice(0, 10)
    .map((item): SearchResult => {
      const isMovie = item.media_type === "movie";
      const title = isMovie ? item.title! : item.name!;
      const mediaType: MediaType = isMovie ? "film" : "tv_series";
      const dateStr = isMovie ? item.release_date : item.first_air_date;
      const year = dateStr ? parseInt(dateStr.substring(0, 4), 10) : null;
      const thumbnailUrl = item.poster_path
        ? `https://image.tmdb.org/t/p/w200${item.poster_path}`
        : null;

      return {
        title,
        media_type: mediaType,
        thumbnail_url: thumbnailUrl,
        source_api: "tmdb",
        source_api_id: String(item.id),
        author_or_creator: null,
        year: year && !isNaN(year) ? year : null,
        source_url: isMovie
          ? `https://www.themoviedb.org/movie/${item.id}`
          : `https://www.themoviedb.org/tv/${item.id}`,
      };
    });
}

async function searchOpenLibrary(
  encodedQuery: string
): Promise<SearchResult[]> {
  const response = await fetch(
    `https://openlibrary.org/search.json?q=${encodedQuery}&limit=5`,
    { next: { revalidate: 3600 } }
  );

  if (!response.ok) return [];

  const data: OpenLibraryResponse = await response.json();

  return data.docs.slice(0, 5).map((doc): SearchResult => {
    const thumbnailUrl = doc.cover_edition_key
      ? `https://covers.openlibrary.org/b/olid/${doc.cover_edition_key}-M.jpg`
      : null;

    return {
      title: doc.title,
      media_type: "book",
      thumbnail_url: thumbnailUrl,
      source_api: "openlibrary",
      source_api_id: doc.key,
      author_or_creator: doc.author_name?.[0] ?? null,
      year: doc.first_publish_year ?? null,
      source_url: `https://openlibrary.org${doc.key}`,
    };
  });
}
