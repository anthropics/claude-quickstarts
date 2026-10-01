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
  Search,
  ChevronDown,
} from "lucide-react";
import { QuickLog } from "@/components/quick-log";
import { EntryDetail } from "@/components/entry-detail";
import { RecentlyConsumed } from "@/components/recently-consumed";
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
  { value: "all", label: "All", color: "#c9a052" },
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
  onClick,
}: {
  entry: Entry;
  index: number;
  onClick: () => void;
}) {
  const isPortrait = entry.media_type === "book" || entry.media_type === "film";
  const thumbWidth = 64;
  const thumbHeight = isPortrait ? 96 : 64;

  return (
    <button
      onClick={onClick}
      className="group relative bg-background-card rounded-xl p-3 border border-border-subtle animate-fade-in-up w-full text-left transition-colors hover:border-border"
      style={{ animationDelay: `${index * 50}ms`, opacity: 0 }}
    >
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
    </button>
  );
}

export function Timeline(props: { userId: string }) {
  void props;
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState<MediaType | "all">("all");
  const [dateRange, setDateRange] = useState<DateRange>("all");
  const [showDateDropdown, setShowDateDropdown] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<Entry | null>(null);

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

  const handleEntryLogged = useCallback(() => {
    fetchEntries();
  }, [fetchEntries]);

  const handleEntryUpdate = useCallback(
    (updated: Entry) => {
      setEntries((prev) =>
        prev.map((e) => (e.id === updated.id ? updated : e))
      );
      setSelectedEntry(updated);
    },
    []
  );

  const handleEntryDelete = useCallback(
    (id: string) => {
      setEntries((prev) => prev.filter((e) => e.id !== id));
    },
    []
  );

  const groupedEntries = groupEntriesByDate(entries);
  let globalIndex = 0;

  const selectedDateLabel =
    DATE_RANGE_OPTIONS.find((o) => o.value === dateRange)?.label || "All time";

  const selectedTypeLabel =
    selectedType === "all"
      ? null
      : MEDIA_TYPE_CONFIG[selectedType]?.label || selectedType;

  return (
    <div className="space-y-6">
      {/* Quick Log */}
      <QuickLog onEntryCreated={handleEntryLogged} />

      {/* Recently Consumed tray (Spotify/YouTube) */}
      <RecentlyConsumed onEntryCreated={handleEntryLogged} />

      {/* Filters */}
      <div className="space-y-3">
        {/* Media type + Date range on same row */}
        <div className="flex items-center gap-2">
          {/* Media type pills */}
          <div className="flex-1 flex gap-1.5 overflow-x-auto pb-1 scrollbar-none -mr-2">
            {MEDIA_TYPE_OPTIONS.map((option) => {
              const isSelected = selectedType === option.value;
              return (
                <button
                  key={option.value}
                  onClick={() => setSelectedType(option.value)}
                  className={`flex-shrink-0 rounded-full px-2.5 py-1 text-xs font-medium transition-all ${
                    isSelected
                      ? "text-white shadow-sm"
                      : "text-foreground-muted/70 border border-border-subtle/50 hover:text-foreground-muted hover:border-border"
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

          {/* Date range dropdown */}
          <div className="relative flex-shrink-0">
            <button
              onClick={() => setShowDateDropdown(!showDateDropdown)}
              className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium text-foreground-muted hover:text-foreground transition-colors border border-border-subtle"
            >
              {selectedDateLabel}
              <ChevronDown size={12} />
            </button>
            {showDateDropdown && (
              <div className="absolute right-0 top-full mt-1 z-30 rounded-lg border border-border bg-background-card shadow-lg animate-scale-in overflow-hidden">
                {DATE_RANGE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => {
                      setDateRange(option.value);
                      setShowDateDropdown(false);
                    }}
                    className={`block w-full px-4 py-2 text-left text-xs transition-colors ${
                      dateRange === option.value
                        ? "bg-primary/10 text-primary"
                        : "text-foreground-muted hover:bg-background-elevated hover:text-foreground"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </div>
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
        <EmptyState
          selectedType={selectedType}
          selectedTypeLabel={selectedTypeLabel}
          dateRange={dateRange}
          onClearFilters={() => {
            setSelectedType("all");
            setDateRange("all");
          }}
        />
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
                      onClick={() => setSelectedEntry(entry)}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Entry detail modal */}
      {selectedEntry && (
        <EntryDetail
          entry={selectedEntry}
          onClose={() => setSelectedEntry(null)}
          onUpdate={handleEntryUpdate}
          onDelete={handleEntryDelete}
        />
      )}
    </div>
  );
}

function EmptyState({
  selectedType,
  selectedTypeLabel,
  dateRange,
  onClearFilters,
}: {
  selectedType: MediaType | "all";
  selectedTypeLabel: string | null;
  dateRange: DateRange;
  onClearFilters: () => void;
}) {
  const hasFilters = selectedType !== "all" || dateRange !== "all";

  if (hasFilters) {
    const dateLabel =
      dateRange === "year"
        ? " this year"
        : dateRange === "month"
          ? " this month"
          : dateRange === "week"
            ? " this week"
            : "";

    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Search size={40} className="text-foreground-subtle/50 mb-4" />
        <p className="text-foreground-muted text-base font-medium">
          No {selectedTypeLabel ? selectedTypeLabel.toLowerCase() + "s" : "entries"} logged
          {dateLabel}
        </p>
        <p className="text-foreground-subtle text-sm mt-1">
          Try a different filter or log something new.
        </p>
        <button
          onClick={onClearFilters}
          className="mt-4 rounded-lg bg-primary/10 px-4 py-2 text-sm font-medium text-primary hover:bg-primary/20 transition-colors"
        >
          Clear filters
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="mb-6 space-y-2">
        <p className="text-foreground text-lg font-serif font-medium">
          What&apos;s the last thing you watched?
        </p>
        <p className="text-foreground-muted text-sm">
          Type in the search bar above to find and log it instantly.
        </p>
      </div>

      {/* Example ghost cards */}
      <div className="w-full max-w-sm space-y-2 opacity-30">
        {[
          { title: "Dune: Part Two", type: "Film", color: "#dc2626" },
          { title: "Sapiens", type: "Book", color: "#d97706" },
          { title: "Serial", type: "Podcast", color: "#16a34a" },
        ].map((example) => (
          <div
            key={example.title}
            className="flex items-center gap-3 rounded-xl bg-background-card border border-border-subtle p-3"
          >
            <div
              className="h-12 w-9 rounded-lg flex-shrink-0"
              style={{ backgroundColor: `${example.color}30` }}
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{example.title}</p>
              <span
                className="text-xs px-1.5 py-0.5 rounded-full"
                style={{
                  backgroundColor: `${example.color}20`,
                  color: example.color,
                }}
              >
                {example.type}
              </span>
            </div>
          </div>
        ))}
      </div>
      <p className="text-foreground-subtle text-xs mt-4">
        Use the search bar to log your first item
      </p>
    </div>
  );
}
