"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import {
  format,
  isToday,
  isYesterday,
  startOfWeek,
  startOfMonth,
  startOfYear,
  parseISO,
} from "date-fns";
import {
  BookOpen,
  Film,
  Tv,
  Podcast,
  Disc3,
  Music,
  Youtube,
  FileText,
  Ticket,
  MoreHorizontal,
  X,
  BookMarked,
} from "lucide-react";
import { QuickLog } from "@/components/quick-log";
import { MediaTypeBadge } from "@/components/media-type-badge";
import { StarRating } from "@/components/star-rating";
import type { Entry, MediaType } from "@/lib/types";
import { MEDIA_TYPE_CONFIG } from "@/lib/types";

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string; style?: React.CSSProperties }>> = {
  BookOpen,
  Film,
  Tv,
  Podcast,
  Disc3,
  Music,
  Youtube,
  FileText,
  Ticket,
  MoreHorizontal,
};

type DateRange = "all" | "year" | "month" | "week";

const DATE_RANGE_OPTIONS: { value: DateRange; label: string }[] = [
  { value: "all", label: "All time" },
  { value: "year", label: "This year" },
  { value: "month", label: "This month" },
  { value: "week", label: "This week" },
];

const MEDIA_TYPE_OPTIONS: { value: MediaType | "all"; label: string; color: string }[] = [
  { value: "all", label: "All", color: "#7c6bf0" },
  ...Object.entries(MEDIA_TYPE_CONFIG).map(([key, config]) => ({
    value: key as MediaType,
    label: config.label,
    color: config.color,
  })),
];

function getDateRangeParam(range: DateRange): string | null {
  const now = new Date();
  switch (range) {
    case "week":
      return startOfWeek(now, { weekStartsOn: 1 }).toISOString();
    case "month":
      return startOfMonth(now).toISOString();
    case "year":
      return startOfYear(now).toISOString();
    default:
      return null;
  }
}

function formatTimeLogged(dateStr: string): string {
  return format(parseISO(dateStr), "h:mm a");
}

function formatGroupDate(dateStr: string): string {
  const date = parseISO(dateStr);
  if (isToday(date)) return "Today";
  if (isYesterday(date)) return "Yesterday";
  return format(date, "EEEE, MMMM d");
}

function groupEntriesByDate(entries: Entry[]): Map<string, Entry[]> {
  const groups = new Map<string, Entry[]>();
  for (const entry of entries) {
    const dateKey = format(parseISO(entry.logged_at), "yyyy-MM-dd");
    const existing = groups.get(dateKey);
    if (existing) {
      existing.push(entry);
    } else {
      groups.set(dateKey, [entry]);
    }
  }
  return groups;
}

function ThumbnailFallback({
  mediaType,
  width,
  height,
}: {
  mediaType: MediaType;
  width: number;
  height: number;
}) {
  const config = MEDIA_TYPE_CONFIG[mediaType];
  const Icon = ICON_MAP[config.icon];

  return (
    <div
      className="flex items-center justify-center rounded-lg flex-shrink-0"
      style={{
        width,
        height,
        backgroundColor: `${config.color}33`,
      }}
    >
      {Icon && <Icon size={24} className="opacity-70" style={{ color: config.color }} />}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-background-card rounded-xl p-3 border border-border-subtle">
      <div className="flex gap-3">
        <div className="w-16 h-24 bg-background-elevated rounded-lg animate-pulse" />
        <div className="flex-1 space-y-2 py-1">
          <div className="h-4 w-3/4 bg-background-elevated rounded animate-pulse" />
          <div className="h-3 w-1/2 bg-background-elevated rounded animate-pulse" />
          <div className="h-5 w-16 bg-background-elevated rounded-full animate-pulse" />
        </div>
      </div>
    </div>
  );
}

function EntryCard({
  entry,
  index,
  onDelete,
}: {
  entry: Entry;
  index: number;
  onDelete: (id: string) => void;
}) {
  const isPortrait = entry.media_type === "book" || entry.media_type === "film";
  const thumbWidth = 64;
  const thumbHeight = isPortrait ? 96 : 64;

  return (
    <div
      className="group relative bg-background-card rounded-xl p-3 border border-border-subtle animate-fade-in-up"
      style={{ animationDelay: `${index * 50}ms`, opacity: 0 }}
    >
      {/* Delete button */}
      <button
        onClick={() => onDelete(entry.id)}
        className="absolute top-2 right-2 p-1 rounded-md text-foreground-subtle opacity-0 group-hover:opacity-100 hover:text-foreground hover:bg-background-elevated transition-all"
        aria-label="Delete entry"
      >
        <X size={14} />
      </button>

      <div className="flex gap-3">
        {/* Thumbnail */}
        {entry.thumbnail_url ? (
          <Image
            src={entry.thumbnail_url}
            alt={entry.title}
            width={thumbWidth}
            height={thumbHeight}
            className="rounded-lg object-cover flex-shrink-0"
            style={{ width: thumbWidth, height: thumbHeight }}
          />
        ) : (
          <ThumbnailFallback
            mediaType={entry.media_type}
            width={thumbWidth}
            height={thumbHeight}
          />
        )}

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3 className="font-serif text-base font-medium leading-snug truncate pr-6">
            {entry.title}
          </h3>

          {(entry.author_or_creator || entry.year) && (
            <p className="text-sm text-foreground-muted truncate mt-0.5">
              {entry.author_or_creator}
              {entry.author_or_creator && entry.year && " \u00B7 "}
              {entry.year}
            </p>
          )}

          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <MediaTypeBadge type={entry.media_type} />
            {entry.rating !== null && entry.rating > 0 && (
              <StarRating rating={entry.rating} size={14} />
            )}
          </div>

          {entry.note && (
            <p className="text-sm text-foreground-muted italic mt-1.5 line-clamp-2">
              {entry.note}
            </p>
          )}

          <p className="text-xs text-foreground-subtle mt-1.5">
            {formatTimeLogged(entry.logged_at)}
          </p>
        </div>
      </div>
    </div>
  );
}

export function Timeline(props: { userId: string }) {
  void props;
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState<MediaType | "all">("all");
  const [dateRange, setDateRange] = useState<DateRange>("all");

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedType !== "all") {
        params.set("type", selectedType);
      }
      const from = getDateRangeParam(dateRange);
      if (from) {
        params.set("from", from);
      }

      const queryString = params.toString();
      const url = `/api/entries${queryString ? `?${queryString}` : ""}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setEntries(data);
      }
    } catch {
      // Silently handle fetch errors
    } finally {
      setLoading(false);
    }
  }, [selectedType, dateRange]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const handleDelete = useCallback(
    async (id: string) => {
      // Optimistic removal
      const previousEntries = entries;
      setEntries((prev) => prev.filter((e) => e.id !== id));

      try {
        const res = await fetch(`/api/entries/${id}`, { method: "DELETE" });
        if (!res.ok) {
          // Revert on failure
          setEntries(previousEntries);
        }
      } catch {
        setEntries(previousEntries);
      }
    },
    [entries]
  );

  const handleEntryLogged = useCallback(() => {
    fetchEntries();
  }, [fetchEntries]);

  const groupedEntries = groupEntriesByDate(entries);
  let globalIndex = 0;

  return (
    <div className="space-y-6">
      {/* Quick Log */}
      <QuickLog onEntryCreated={handleEntryLogged} />

      {/* Filters */}
      <div className="space-y-3">
        {/* Media type filter */}
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none -mx-4 px-4">
          {MEDIA_TYPE_OPTIONS.map((option) => {
            const isSelected = selectedType === option.value;
            return (
              <button
                key={option.value}
                onClick={() => setSelectedType(option.value)}
                className={`flex-shrink-0 rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                  isSelected
                    ? "text-white"
                    : "text-foreground-muted hover:text-foreground bg-background-card border border-border-subtle"
                }`}
                style={
                  isSelected
                    ? { backgroundColor: option.color }
                    : undefined
                }
              >
                {option.label}
              </button>
            );
          })}
        </div>

        {/* Date range filter */}
        <div className="flex gap-2">
          {DATE_RANGE_OPTIONS.map((option) => {
            const isSelected = dateRange === option.value;
            return (
              <button
                key={option.value}
                onClick={() => setDateRange(option.value)}
                className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
                  isSelected
                    ? "bg-primary text-white"
                    : "text-foreground-muted hover:text-foreground hover:bg-background-elevated"
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Entries */}
      {loading ? (
        <div className="space-y-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : entries.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <BookMarked size={48} className="text-foreground-subtle mb-4" />
          <p className="text-foreground-muted text-lg font-medium">
            Your media diary is empty.
          </p>
          <p className="text-foreground-subtle text-sm mt-1">
            Start logging!
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {Array.from(groupedEntries.entries()).map(([dateKey, dateEntries]) => (
            <div key={dateKey}>
              <h2 className="text-sm font-medium text-foreground-muted mb-3 sticky top-14 bg-background/90 backdrop-blur-sm py-2 z-10">
                {formatGroupDate(dateKey)}
              </h2>
              <div className="space-y-3">
                {dateEntries.map((entry) => {
                  const cardIndex = globalIndex++;
                  return (
                    <EntryCard
                      key={entry.id}
                      entry={entry}
                      index={cardIndex}
                      onDelete={handleDelete}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
