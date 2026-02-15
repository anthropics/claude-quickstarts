"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Image from "next/image";
import { Search, Plus, Check, X, Link as LinkIcon } from "lucide-react";
import { MediaTypeBadge } from "@/components/media-type-badge";
import { StarRating } from "@/components/star-rating";
import {
  SearchResult,
  MediaType,
  MEDIA_TYPE_CONFIG,
} from "@/lib/types";

type View = "search" | "confirm" | "manual";

interface QuickLogProps {
  onEntryCreated: () => void;
}

function isUrl(value: string): boolean {
  return /^https?:\/\//i.test(value.trim());
}

export function QuickLog({ onEntryCreated }: QuickLogProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("search");
  const [showDropdown, setShowDropdown] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [successFlash, setSuccessFlash] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Confirm log state
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(
    null,
  );
  const [note, setNote] = useState("");
  const [rating, setRating] = useState<number | null>(null);

  // Manual entry state
  const [manualTitle, setManualTitle] = useState("");
  const [manualType, setManualType] = useState<MediaType>("other");
  const [manualAuthor, setManualAuthor] = useState("");
  const [manualYear, setManualYear] = useState("");
  const [manualNote, setManualNote] = useState("");
  const [manualRating, setManualRating] = useState<number | null>(null);
  const [manualUrl, setManualUrl] = useState("");

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resetToSearch = useCallback(() => {
    setView("search");
    setSelectedResult(null);
    setNote("");
    setRating(null);
    setManualTitle("");
    setManualType("other");
    setManualAuthor("");
    setManualYear("");
    setManualNote("");
    setManualRating(null);
    setManualUrl("");
  }, []);

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
        if (view !== "search") {
          resetToSearch();
        }
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [view, resetToSearch]);

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setHasSearched(false);
      setShowDropdown(false);
      setLoading(false);
      return;
    }

    setLoading(true);
    setShowDropdown(true);

    debounceRef.current = setTimeout(async () => {
      try {
        const fetchUrl = isUrl(trimmed)
          ? `/api/search/url?url=${encodeURIComponent(trimmed)}`
          : `/api/search?q=${encodeURIComponent(trimmed)}`;

        const res = await fetch(fetchUrl);
        if (res.ok) {
          const data = await res.json();
          // URL endpoint returns a single result, search returns an array
          if (Array.isArray(data)) {
            setResults(data);
          } else {
            setResults([data]);
          }
        } else {
          setResults([]);
        }
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
        setHasSearched(true);
      }
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query]);

  const handleSelectResult = (result: SearchResult) => {
    setSelectedResult(result);
    setNote("");
    setRating(null);
    setView("confirm");
  };

  const handleManualEntry = () => {
    setManualTitle(query);
    setManualType("other");
    setManualAuthor("");
    setManualYear("");
    setManualNote("");
    setManualRating(null);
    setManualUrl("");
    setView("manual");
  };

  const handleLogConfirm = async () => {
    if (!selectedResult || submitting) return;
    setSubmitting(true);

    try {
      const res = await fetch("/api/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: selectedResult.title,
          media_type: selectedResult.media_type,
          thumbnail_url: selectedResult.thumbnail_url,
          note: note.trim() || null,
          rating: rating,
          source_url: selectedResult.source_url,
          source_api: selectedResult.source_api,
          source_api_id: selectedResult.source_api_id,
          author_or_creator: selectedResult.author_or_creator,
          year: selectedResult.year,
        }),
      });

      if (res.ok) {
        showSuccess();
      }
    } catch {
      // Silently fail - user can retry
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogManual = async () => {
    if (!manualTitle.trim() || submitting) return;
    setSubmitting(true);

    const parsedYear = manualYear ? parseInt(manualYear, 10) : null;

    try {
      const res = await fetch("/api/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: manualTitle.trim(),
          media_type: manualType,
          thumbnail_url: null,
          note: manualNote.trim() || null,
          rating: manualRating,
          source_url: manualUrl.trim() || null,
          source_api: "manual",
          source_api_id: null,
          author_or_creator: manualAuthor.trim() || null,
          year: parsedYear && !isNaN(parsedYear) ? parsedYear : null,
        }),
      });

      if (res.ok) {
        showSuccess();
      }
    } catch {
      // Silently fail - user can retry
    } finally {
      setSubmitting(false);
    }
  };

  const showSuccess = () => {
    setSuccessFlash(true);
    setTimeout(() => {
      setSuccessFlash(false);
      setQuery("");
      setResults([]);
      setHasSearched(false);
      setShowDropdown(false);
      resetToSearch();
      onEntryCreated();
    }, 600);
  };

  const mediaTypes = Object.entries(MEDIA_TYPE_CONFIG) as [
    MediaType,
    (typeof MEDIA_TYPE_CONFIG)[MediaType],
  ][];

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Search input - Spotlight style */}
      <div
        className={`relative transition-transform duration-300 ${successFlash ? "scale-105" : "scale-100"}`}
      >
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
          {successFlash ? (
            <Check size={20} className="text-green-400" />
          ) : (
            <Search size={20} className="text-foreground-muted" />
          )}
        </div>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (view !== "search") {
              resetToSearch();
            }
          }}
          onFocus={() => {
            if (query.trim() && (results.length > 0 || hasSearched)) {
              setShowDropdown(true);
            }
          }}
          placeholder="What did you watch, read, or listen to?"
          className={`w-full rounded-xl bg-background-elevated py-4 pl-12 pr-4 text-lg text-foreground placeholder:text-foreground-subtle transition-all duration-200 ${
            successFlash
              ? "ring-2 ring-green-400/60"
              : showDropdown
                ? "ring-2 ring-primary/40"
                : ""
          }`}
        />
        {loading && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-4">
            <div className="h-5 w-5 animate-pulse rounded-full bg-primary/40" />
          </div>
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && !successFlash && (
        <div className="absolute left-0 right-0 z-50 mt-2 animate-scale-in overflow-hidden rounded-xl border border-border bg-background-card shadow-xl">
          {/* Search view */}
          {view === "search" && (
            <div className="max-h-[420px] overflow-y-auto">
              {/* Loading skeleton */}
              {loading && results.length === 0 && (
                <div className="space-y-1 p-2">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="flex animate-pulse items-center gap-3 rounded-lg p-3"
                    >
                      <div className="h-16 w-12 rounded-md bg-background-elevated" />
                      <div className="flex-1 space-y-2">
                        <div className="h-4 w-3/4 rounded bg-background-elevated" />
                        <div className="h-3 w-1/2 rounded bg-background-elevated" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Results list */}
              {!loading && results.length > 0 && (
                <div className="p-2">
                  {results.map((result, idx) => (
                    <button
                      key={`${result.source_api}-${result.source_api_id}-${idx}`}
                      onClick={() => handleSelectResult(result)}
                      className="flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors hover:bg-background-elevated"
                    >
                      {result.thumbnail_url ? (
                        <Image
                          src={result.thumbnail_url}
                          alt={result.title}
                          width={48}
                          height={64}
                          className="h-16 w-12 rounded-md object-cover"
                        />
                      ) : (
                        <div className="flex h-16 w-12 items-center justify-center rounded-md bg-background-elevated text-foreground-subtle">
                          <Search size={16} />
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium text-foreground">
                          {result.title}
                        </p>
                        <p className="truncate text-sm text-foreground-muted">
                          {[result.author_or_creator, result.year]
                            .filter(Boolean)
                            .join(" · ") || "\u00A0"}
                        </p>
                        <div className="mt-1">
                          <MediaTypeBadge type={result.media_type} />
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {/* No results */}
              {!loading && hasSearched && results.length === 0 && (
                <div className="px-4 py-6 text-center text-foreground-muted">
                  <p className="text-sm">No results found</p>
                </div>
              )}

              {/* Manual entry option */}
              {hasSearched && !loading && (
                <div className="border-t border-border p-2">
                  <button
                    onClick={handleManualEntry}
                    className="flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors hover:bg-background-elevated"
                  >
                    <div className="flex h-16 w-12 items-center justify-center rounded-md bg-background-elevated text-primary">
                      <Plus size={20} />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">
                        Manual entry
                      </p>
                      <p className="text-sm text-foreground-muted">
                        Add &quot;{query.trim()}&quot; yourself
                      </p>
                    </div>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Confirm log view */}
          {view === "confirm" && selectedResult && (
            <div className="animate-scale-in p-4">
              <div className="mb-4 flex items-start gap-3">
                {selectedResult.thumbnail_url ? (
                  <Image
                    src={selectedResult.thumbnail_url}
                    alt={selectedResult.title}
                    width={48}
                    height={64}
                    className="h-16 w-12 rounded-md object-cover"
                  />
                ) : (
                  <div className="flex h-16 w-12 items-center justify-center rounded-md bg-background-elevated text-foreground-subtle">
                    <Search size={16} />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-foreground">
                    {selectedResult.title}
                  </p>
                  <p className="text-sm text-foreground-muted">
                    {[selectedResult.author_or_creator, selectedResult.year]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  <div className="mt-1">
                    <MediaTypeBadge type={selectedResult.media_type} />
                  </div>
                </div>
              </div>

              {/* Rating */}
              <div className="mb-3">
                <label className="mb-1.5 block text-sm text-foreground-muted">
                  Rating (optional)
                </label>
                <StarRating rating={rating} onRate={setRating} size={24} />
              </div>

              {/* Note */}
              <div className="mb-4">
                <label className="mb-1.5 block text-sm text-foreground-muted">
                  Quick note (optional)
                </label>
                <div className="relative">
                  <textarea
                    value={note}
                    onChange={(e) =>
                      setNote(e.target.value.slice(0, 280))
                    }
                    placeholder="Any thoughts?"
                    rows={2}
                    className="w-full resize-none rounded-lg bg-background-elevated p-3 text-sm text-foreground placeholder:text-foreground-subtle"
                  />
                  <span className="absolute bottom-2 right-2 text-xs text-foreground-subtle">
                    {note.length}/280
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleLogConfirm}
                  disabled={submitting}
                  className="flex-1 rounded-lg bg-primary px-4 py-2 font-medium text-white transition-colors hover:bg-primary-hover disabled:opacity-50"
                >
                  {submitting ? "Logging..." : "Log it"}
                </button>
                <button
                  onClick={resetToSearch}
                  className="rounded-lg px-4 py-2 text-foreground-muted transition-colors hover:bg-background-elevated hover:text-foreground"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Manual entry view */}
          {view === "manual" && (
            <div className="animate-scale-in p-4">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="font-medium text-foreground">Manual entry</h3>
                <button
                  onClick={resetToSearch}
                  className="rounded-lg p-1 text-foreground-muted transition-colors hover:bg-background-elevated hover:text-foreground"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Title */}
              <div className="mb-3">
                <label className="mb-1.5 block text-sm text-foreground-muted">
                  Title
                </label>
                <input
                  type="text"
                  value={manualTitle}
                  onChange={(e) => setManualTitle(e.target.value)}
                  placeholder="Title"
                  className="w-full rounded-lg bg-background-elevated px-3 py-2 text-sm text-foreground placeholder:text-foreground-subtle"
                />
              </div>

              {/* Media type selector */}
              <div className="mb-3">
                <label className="mb-1.5 block text-sm text-foreground-muted">
                  Type
                </label>
                <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-6">
                  {mediaTypes.map(([type, config]) => (
                    <button
                      key={type}
                      onClick={() => setManualType(type)}
                      className={`rounded-lg px-2 py-1.5 text-xs font-medium transition-all ${
                        manualType === type
                          ? "ring-2 ring-offset-1 ring-offset-background-card"
                          : "opacity-60 hover:opacity-100"
                      }`}
                      style={{
                        backgroundColor: `${config.color}20`,
                        color: config.color,
                        ...(manualType === type
                          ? { ringColor: config.color }
                          : {}),
                      }}
                    >
                      {config.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Author / Creator */}
              <div className="mb-3">
                <label className="mb-1.5 block text-sm text-foreground-muted">
                  Author / Creator (optional)
                </label>
                <input
                  type="text"
                  value={manualAuthor}
                  onChange={(e) => setManualAuthor(e.target.value)}
                  placeholder="Author, director, artist..."
                  className="w-full rounded-lg bg-background-elevated px-3 py-2 text-sm text-foreground placeholder:text-foreground-subtle"
                />
              </div>

              {/* Year */}
              <div className="mb-3">
                <label className="mb-1.5 block text-sm text-foreground-muted">
                  Year (optional)
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  value={manualYear}
                  onChange={(e) =>
                    setManualYear(e.target.value.replace(/\D/g, "").slice(0, 4))
                  }
                  placeholder="2024"
                  className="w-full rounded-lg bg-background-elevated px-3 py-2 text-sm text-foreground placeholder:text-foreground-subtle"
                />
              </div>

              {/* Rating */}
              <div className="mb-3">
                <label className="mb-1.5 block text-sm text-foreground-muted">
                  Rating (optional)
                </label>
                <StarRating
                  rating={manualRating}
                  onRate={setManualRating}
                  size={24}
                />
              </div>

              {/* Note */}
              <div className="mb-3">
                <label className="mb-1.5 block text-sm text-foreground-muted">
                  Note (optional)
                </label>
                <div className="relative">
                  <textarea
                    value={manualNote}
                    onChange={(e) =>
                      setManualNote(e.target.value.slice(0, 280))
                    }
                    placeholder="Any thoughts?"
                    rows={2}
                    className="w-full resize-none rounded-lg bg-background-elevated p-3 text-sm text-foreground placeholder:text-foreground-subtle"
                  />
                  <span className="absolute bottom-2 right-2 text-xs text-foreground-subtle">
                    {manualNote.length}/280
                  </span>
                </div>
              </div>

              {/* URL */}
              <div className="mb-4">
                <label className="mb-1.5 block text-sm text-foreground-muted">
                  <span className="flex items-center gap-1">
                    <LinkIcon size={12} />
                    URL (optional)
                  </span>
                </label>
                <input
                  type="url"
                  value={manualUrl}
                  onChange={(e) => setManualUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full rounded-lg bg-background-elevated px-3 py-2 text-sm text-foreground placeholder:text-foreground-subtle"
                />
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleLogManual}
                  disabled={!manualTitle.trim() || submitting}
                  className="flex-1 rounded-lg bg-primary px-4 py-2 font-medium text-white transition-colors hover:bg-primary-hover disabled:opacity-50"
                >
                  {submitting ? "Logging..." : "Log it"}
                </button>
                <button
                  onClick={resetToSearch}
                  className="rounded-lg px-4 py-2 text-foreground-muted transition-colors hover:bg-background-elevated hover:text-foreground"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
