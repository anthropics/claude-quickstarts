"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Image from "next/image";
import {
  Search,
  Plus,
  Check,
  X,
  Link as LinkIcon,
  Loader2,
  Clipboard,
} from "lucide-react";
import { toast } from "sonner";
import { StarRating } from "@/components/star-rating";
import {
  SearchResult,
  MediaType,
  MEDIA_TYPE_CONFIG,
  Entry,
} from "@/lib/types";

type View = "search" | "manual" | "enrich";

const NOTE_PLACEHOLDERS: Record<string, string> = {
  book: "What's the one idea you'll remember?",
  film: "How did it make you feel?",
  podcast: "What surprised you?",
  album: "When/where did you listen?",
  song: "When/where did you listen?",
  youtube: "Why was this worth watching?",
  tv_series: "How did it make you feel?",
  tv_episode: "How did it make you feel?",
  article: "What's the key takeaway?",
  live_event: "What was the highlight?",
  other: "What will you want to remember?",
};

interface QuickLogProps {
  onEntryCreated: (entry: Entry) => void;
}

function isUrl(value: string): boolean {
  return /^https?:\/\//i.test(value.trim());
}

function groupResultsByType(
  results: SearchResult[]
): Map<string, SearchResult[]> {
  const groups = new Map<string, SearchResult[]>();
  for (const result of results) {
    const label =
      MEDIA_TYPE_CONFIG[result.media_type]?.label || result.media_type;
    const existing = groups.get(label);
    if (existing) {
      existing.push(result);
    } else {
      groups.set(label, [result]);
    }
  }
  return groups;
}

export function QuickLog({ onEntryCreated }: QuickLogProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("search");
  const [showDropdown, setShowDropdown] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [hasGlowed, setHasGlowed] = useState(false);

  // URL paste detection
  const [clipboardUrl, setClipboardUrl] = useState<string | null>(null);
  const [clipboardResult, setClipboardResult] = useState<SearchResult | null>(
    null
  );
  const [clipboardLoading, setClipboardLoading] = useState(false);

  // Enrich state (post-log note/rating prompt)
  const [enrichEntry, setEnrichEntry] = useState<Entry | null>(null);
  const [enrichNote, setEnrichNote] = useState("");
  const [enrichRating, setEnrichRating] = useState<number | null>(null);
  const [enrichSaving, setEnrichSaving] = useState(false);

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

  const mediaTypes = Object.entries(MEDIA_TYPE_CONFIG) as [
    MediaType,
    (typeof MEDIA_TYPE_CONFIG)[MediaType],
  ][];

  const resetToSearch = useCallback(() => {
    setView("search");
    setEnrichEntry(null);
    setEnrichNote("");
    setEnrichRating(null);
    setManualTitle("");
    setManualType("other");
    setManualAuthor("");
    setManualYear("");
    setManualNote("");
    setManualRating(null);
    setManualUrl("");
  }, []);

  // Mark that glow has played after first render
  useEffect(() => {
    const timer = setTimeout(() => setHasGlowed(true), 8000);
    return () => clearTimeout(timer);
  }, []);

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
        setClipboardUrl(null);
        setClipboardResult(null);
        if (view === "manual") {
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

  // URL paste detection on focus
  const handleFocus = useCallback(async () => {
    if (query.trim() && (results.length > 0 || hasSearched)) {
      setShowDropdown(true);
    }

    // Check clipboard for URL
    try {
      const text = await navigator.clipboard.readText();
      if (text && /^https?:\/\//i.test(text.trim()) && text.trim() !== query.trim()) {
        setClipboardUrl(text.trim());
        setClipboardLoading(true);
        // Fetch metadata
        const res = await fetch(
          `/api/search/url?url=${encodeURIComponent(text.trim())}`
        );
        if (res.ok) {
          const data = await res.json();
          setClipboardResult(data);
        }
        setClipboardLoading(false);
      }
    } catch {
      // Clipboard access denied — that's fine
    }
  }, [query, results.length, hasSearched]);

  // One-tap log a search result
  const handleQuickLog = async (result: SearchResult) => {
    const logKey = `${result.source_api}-${result.source_api_id}-${result.title}`;
    if (submitting) return;
    setSubmitting(logKey);

    try {
      const res = await fetch("/api/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: result.title,
          media_type: result.media_type,
          thumbnail_url: result.thumbnail_url,
          note: null,
          rating: null,
          source_url: result.source_url,
          source_api: result.source_api,
          source_api_id: result.source_api_id,
          author_or_creator: result.author_or_creator,
          year: result.year,
        }),
      });

      if (res.ok) {
        const entry: Entry = await res.json();
        toast.success("Logged!", {
          icon: <Check size={16} className="text-green-400" />,
          duration: 2000,
        });
        setQuery("");
        setResults([]);
        setHasSearched(false);
        setShowDropdown(false);
        setClipboardUrl(null);
        setClipboardResult(null);
        onEntryCreated(entry);

        // Show enrich prompt
        setEnrichEntry(entry);
        setView("enrich");
      }
    } catch {
      toast.error("Failed to log. Try again.");
    } finally {
      setSubmitting(null);
    }
  };

  // Log from clipboard detection
  const handleClipboardLog = () => {
    if (clipboardResult) {
      handleQuickLog(clipboardResult);
    }
  };

  const dismissClipboard = () => {
    setClipboardUrl(null);
    setClipboardResult(null);
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

  const handleLogManual = async () => {
    if (!manualTitle.trim() || submitting) return;
    setSubmitting("manual");

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
        const entry: Entry = await res.json();
        toast.success("Logged!", {
          icon: <Check size={16} className="text-green-400" />,
          duration: 2000,
        });
        setQuery("");
        setResults([]);
        setHasSearched(false);
        setShowDropdown(false);
        resetToSearch();
        onEntryCreated(entry);
      }
    } catch {
      toast.error("Failed to log. Try again.");
    } finally {
      setSubmitting(null);
    }
  };

  // Save enrichment (note + rating) to an already-logged entry
  const handleSaveEnrich = async () => {
    if (!enrichEntry || enrichSaving) return;
    setEnrichSaving(true);

    const updates: Record<string, unknown> = {};
    if (enrichNote.trim()) updates.note = enrichNote.trim();
    if (enrichRating !== null) updates.rating = enrichRating;

    if (Object.keys(updates).length === 0) {
      setView("search");
      setEnrichEntry(null);
      setEnrichSaving(false);
      return;
    }

    try {
      const res = await fetch(`/api/entries/${enrichEntry.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });

      if (res.ok) {
        toast.success("Note saved!");
        onEntryCreated(enrichEntry); // Refresh timeline
      }
    } catch {
      toast.error("Failed to save note.");
    } finally {
      setEnrichSaving(false);
      setView("search");
      setEnrichEntry(null);
      setEnrichNote("");
      setEnrichRating(null);
    }
  };

  const dismissEnrich = () => {
    setView("search");
    setEnrichEntry(null);
    setEnrichNote("");
    setEnrichRating(null);
  };

  const groupedResults = groupResultsByType(results);

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Search input - Spotlight style */}
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
          <Search size={20} className="text-foreground-muted" />
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
          onFocus={handleFocus}
          placeholder="What did you watch, read, or listen to?"
          className={`w-full rounded-xl bg-background-elevated py-4 pl-12 pr-4 text-lg text-foreground placeholder:text-foreground-subtle transition-all duration-200 ${
            showDropdown
              ? "ring-2 ring-primary/40"
              : !hasGlowed
                ? "animate-subtle-glow"
                : ""
          }`}
        />
        {loading && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-4">
            <Loader2 size={18} className="animate-spin text-primary" />
          </div>
        )}
      </div>

      {/* Clipboard URL detection banner */}
      {clipboardUrl && !showDropdown && (
        <div className="mt-2 flex items-center gap-3 rounded-xl border border-border bg-background-card p-3 animate-scale-in">
          <Clipboard size={16} className="text-primary flex-shrink-0" />
          {clipboardLoading ? (
            <div className="flex-1 flex items-center gap-2 text-sm text-foreground-muted">
              <Loader2 size={14} className="animate-spin" />
              Checking clipboard link...
            </div>
          ) : clipboardResult ? (
            <>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {clipboardResult.title}
                </p>
                <p className="text-xs text-foreground-muted truncate">
                  {clipboardResult.author_or_creator || clipboardUrl}
                </p>
              </div>
              <button
                onClick={handleClipboardLog}
                disabled={submitting !== null}
                className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-hover disabled:opacity-50"
              >
                <Plus size={14} />
                Log this
              </button>
              <button
                onClick={dismissClipboard}
                className="p-1 text-foreground-subtle hover:text-foreground"
              >
                <X size={14} />
              </button>
            </>
          ) : null}
        </div>
      )}

      {/* Post-log enrich prompt */}
      {view === "enrich" && enrichEntry && (
        <div className="mt-2 rounded-xl border border-border bg-background-card p-4 animate-scale-in">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-foreground">
              Add a note?{" "}
              <span className="text-foreground-subtle font-normal">
                (optional)
              </span>
            </p>
            <button
              onClick={dismissEnrich}
              className="p-1 text-foreground-subtle hover:text-foreground"
            >
              <X size={14} />
            </button>
          </div>

          <div className="mb-3">
            <StarRating rating={enrichRating} onRate={setEnrichRating} size={22} />
          </div>

          <div className="relative mb-3">
            <textarea
              value={enrichNote}
              onChange={(e) => setEnrichNote(e.target.value.slice(0, 280))}
              placeholder={
                NOTE_PLACEHOLDERS[enrichEntry.media_type] ||
                NOTE_PLACEHOLDERS.other
              }
              rows={2}
              className="w-full resize-none rounded-lg bg-background-elevated p-3 text-sm text-foreground placeholder:text-foreground-subtle"
              autoFocus
            />
            <span className="absolute bottom-2 right-2 text-xs text-foreground-subtle">
              {enrichNote.length}/280
            </span>
          </div>

          <button
            onClick={handleSaveEnrich}
            disabled={enrichSaving}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-hover disabled:opacity-50"
          >
            {enrichSaving ? "Saving..." : "Save"}
          </button>
        </div>
      )}

      {/* Dropdown */}
      {showDropdown && view !== "enrich" && (
        <div className="absolute left-0 right-0 z-50 mt-2 animate-scale-in overflow-hidden rounded-xl border border-border bg-background-card shadow-xl">
          {/* Search view */}
          {view === "search" && (
            <div className="max-h-[480px] overflow-y-auto">
              {/* Clipboard URL banner inside dropdown */}
              {clipboardUrl && clipboardResult && (
                <div className="border-b border-border p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Clipboard size={14} className="text-primary" />
                    <span className="text-xs font-medium text-foreground-muted uppercase tracking-wider">
                      From clipboard
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    {clipboardResult.thumbnail_url ? (
                      <Image
                        src={clipboardResult.thumbnail_url}
                        alt={clipboardResult.title}
                        width={40}
                        height={40}
                        className="h-10 w-10 rounded-md object-cover"
                      />
                    ) : (
                      <div className="flex h-10 w-10 items-center justify-center rounded-md bg-background-elevated text-foreground-subtle">
                        <LinkIcon size={14} />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {clipboardResult.title}
                      </p>
                      <p className="text-xs text-foreground-muted truncate">
                        {clipboardResult.author_or_creator}
                      </p>
                    </div>
                    <button
                      onClick={handleClipboardLog}
                      disabled={submitting !== null}
                      className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-white transition-colors hover:bg-primary-hover disabled:opacity-50"
                    >
                      <Plus size={16} />
                    </button>
                  </div>
                </div>
              )}

              {/* Loading skeleton */}
              {loading && results.length === 0 && (
                <div className="space-y-1 p-2">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="flex animate-pulse items-center gap-3 rounded-lg p-3"
                    >
                      <div className="h-12 w-12 rounded-md bg-background-elevated" />
                      <div className="flex-1 space-y-2">
                        <div className="h-4 w-3/4 rounded bg-background-elevated" />
                        <div className="h-3 w-1/2 rounded bg-background-elevated" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Grouped results */}
              {!loading && results.length > 0 && (
                <div className="p-1">
                  {Array.from(groupedResults.entries()).map(
                    ([groupLabel, groupResults]) => (
                      <div key={groupLabel}>
                        <div className="px-3 pt-3 pb-1">
                          <span className="text-xs font-medium text-foreground-subtle uppercase tracking-wider">
                            {groupLabel}s
                          </span>
                        </div>
                        {groupResults.map((result, idx) => {
                          const logKey = `${result.source_api}-${result.source_api_id}-${result.title}`;
                          const isLogging = submitting === logKey;

                          return (
                            <div
                              key={`${result.source_api}-${result.source_api_id}-${idx}`}
                              className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-background-elevated group"
                            >
                              {result.thumbnail_url ? (
                                <Image
                                  src={result.thumbnail_url}
                                  alt={result.title}
                                  width={44}
                                  height={44}
                                  className="h-11 w-11 rounded-md object-cover flex-shrink-0"
                                />
                              ) : (
                                <div className="flex h-11 w-11 items-center justify-center rounded-md bg-background-elevated text-foreground-subtle flex-shrink-0">
                                  <Search size={14} />
                                </div>
                              )}
                              <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-medium text-foreground">
                                  {result.title}
                                </p>
                                <p className="truncate text-xs text-foreground-muted">
                                  {[result.author_or_creator, result.year]
                                    .filter(Boolean)
                                    .join(" \u00B7 ") || "\u00A0"}
                                </p>
                              </div>
                              <button
                                onClick={() => handleQuickLog(result)}
                                disabled={submitting !== null}
                                className={`flex h-8 w-8 items-center justify-center rounded-lg transition-all flex-shrink-0 ${
                                  isLogging
                                    ? "bg-green-500/20 text-green-400"
                                    : "bg-primary/10 text-primary opacity-0 group-hover:opacity-100 hover:bg-primary hover:text-white"
                                } disabled:opacity-50`}
                                title="Log this"
                              >
                                {isLogging ? (
                                  <Loader2
                                    size={14}
                                    className="animate-spin"
                                  />
                                ) : (
                                  <Plus size={16} />
                                )}
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    )
                  )}
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
                    <div className="flex h-11 w-11 items-center justify-center rounded-md bg-background-elevated text-primary flex-shrink-0">
                      <Plus size={18} />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        Manual entry
                      </p>
                      <p className="text-xs text-foreground-muted">
                        Add &quot;{query.trim()}&quot; yourself
                      </p>
                    </div>
                  </button>
                </div>
              )}
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
                    placeholder={
                      NOTE_PLACEHOLDERS[manualType] || NOTE_PLACEHOLDERS.other
                    }
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
                  disabled={!manualTitle.trim() || submitting !== null}
                  className="flex-1 rounded-lg bg-primary px-4 py-2 font-medium text-white transition-colors hover:bg-primary-hover disabled:opacity-50"
                >
                  {submitting === "manual" ? "Logging..." : "Log it"}
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
