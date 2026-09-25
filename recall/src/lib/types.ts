export type MediaType =
  | "book"
  | "film"
  | "tv_series"
  | "tv_episode"
  | "podcast"
  | "album"
  | "song"
  | "youtube"
  | "article"
  | "live_event"
  | "other";

export interface Entry {
  id: string;
  user_id: string;
  title: string;
  media_type: MediaType;
  thumbnail_url: string | null;
  note: string | null;
  rating: number | null;
  logged_at: string;
  source_url: string | null;
  source_api: "openlibrary" | "tmdb" | "spotify" | "youtube" | "manual" | null;
  source_api_id: string | null;
  author_or_creator: string | null;
  year: number | null;
  created_at: string;
}

export interface SearchResult {
  title: string;
  media_type: MediaType;
  thumbnail_url: string | null;
  source_api: Entry["source_api"];
  source_api_id: string | null;
  author_or_creator: string | null;
  year: number | null;
  source_url: string | null;
}

export const MEDIA_TYPE_CONFIG: Record<
  MediaType,
  { label: string; color: string; icon: string }
> = {
  book: { label: "Book", color: "#d97706", icon: "BookOpen" },
  film: { label: "Film", color: "#dc2626", icon: "Film" },
  tv_series: { label: "TV Series", color: "#4f46e5", icon: "Tv" },
  tv_episode: { label: "TV Episode", color: "#6366f1", icon: "Tv" },
  podcast: { label: "Podcast", color: "#16a34a", icon: "Podcast" },
  album: { label: "Album", color: "#7c3aed", icon: "Disc3" },
  song: { label: "Song", color: "#8b5cf6", icon: "Music" },
  youtube: { label: "YouTube", color: "#f97316", icon: "Youtube" },
  article: { label: "Article", color: "#0d9488", icon: "FileText" },
  live_event: { label: "Live Event", color: "#eab308", icon: "Ticket" },
  other: { label: "Other", color: "#6b7280", icon: "MoreHorizontal" },
};
