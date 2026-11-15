"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import { Search, X } from "lucide-react";
import { Entry } from "@/lib/types";
import { MediaTypeBadge } from "@/components/media-type-badge";
import { StarRating } from "@/components/star-rating";
import { format } from "date-fns";

export function SearchView() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const searchEntries = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setSearched(false);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`/api/entries?q=${encodeURIComponent(q)}`);
      if (res.ok) {
        const data = await res.json();
        setResults(data);
      }
    } catch {
      // Silently handle search errors
    } finally {
      setLoading(false);
      setSearched(true);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      searchEntries(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query, searchEntries]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold font-serif mb-1">Search</h2>
        <p className="text-foreground-muted text-sm">
          Search your media diary by title or notes
        </p>
      </div>

      {/* Search input */}
      <div className="relative">
        <Search
          size={18}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-foreground-subtle"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search titles, notes..."
          className="w-full rounded-xl bg-background-card border border-border py-3 pl-11 pr-10 text-foreground placeholder:text-foreground-subtle"
        />
        {query && (
          <button
            onClick={() => {
              setQuery("");
              setResults([]);
              setSearched(false);
            }}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-foreground-subtle hover:text-foreground"
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* Results */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="flex gap-3 rounded-xl bg-background-card border border-border-subtle p-3 animate-pulse"
            >
              <div className="h-16 w-12 rounded-md bg-background-elevated" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-2/3 rounded bg-background-elevated" />
                <div className="h-3 w-1/3 rounded bg-background-elevated" />
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div className="text-center py-12">
          <Search size={48} className="mx-auto mb-4 text-foreground-subtle" />
          <p className="text-foreground-muted">
            No results found for &ldquo;{query}&rdquo;
          </p>
          <p className="text-foreground-subtle text-sm mt-1">
            Try different keywords or check your spelling
          </p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm text-foreground-subtle">
            {results.length} result{results.length !== 1 ? "s" : ""}
          </p>
          {results.map((entry, index) => (
            <div
              key={entry.id}
              className="flex gap-3 rounded-xl bg-background-card border border-border-subtle p-3 animate-fade-in-up"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              {/* Thumbnail */}
              {entry.thumbnail_url ? (
                <Image
                  src={entry.thumbnail_url}
                  alt={entry.title}
                  width={48}
                  height={64}
                  className="h-16 w-12 rounded-md object-cover flex-shrink-0"
                />
              ) : (
                <div className="h-16 w-12 rounded-md bg-background-elevated flex-shrink-0" />
              )}

              {/* Details */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-serif font-medium text-sm truncate">
                    {entry.title}
                  </h3>
                  <MediaTypeBadge type={entry.media_type} size="sm" />
                </div>
                {entry.author_or_creator && (
                  <p className="text-xs text-foreground-muted mt-0.5">
                    {entry.author_or_creator}
                    {entry.year ? ` (${entry.year})` : ""}
                  </p>
                )}
                {entry.note && (
                  <p className="text-xs text-foreground-muted italic mt-1 truncate">
                    {entry.note}
                  </p>
                )}
                <div className="flex items-center gap-3 mt-1.5">
                  {entry.rating && (
                    <StarRating rating={entry.rating} size={12} />
                  )}
                  <span className="text-xs text-foreground-subtle">
                    {format(new Date(entry.logged_at), "MMM d, yyyy")}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
