"use client";

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
} from "lucide-react";
import { MediaType, MEDIA_TYPE_CONFIG } from "@/lib/types";

const ICON_MAP = {
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
} as Record<string, React.ComponentType<{ size?: number }>>;

export function MediaTypeBadge({
  type,
  size = "sm",
}: {
  type: MediaType;
  size?: "sm" | "md";
}) {
  const config = MEDIA_TYPE_CONFIG[type];
  const Icon = ICON_MAP[config.icon];
  const sizeClasses =
    size === "sm" ? "px-2 py-0.5 text-xs gap-1" : "px-2.5 py-1 text-sm gap-1.5";

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${sizeClasses}`}
      style={{
        backgroundColor: `${config.color}20`,
        color: config.color,
      }}
    >
      {Icon && <Icon size={size === "sm" ? 12 : 14} />}
      {config.label}
    </span>
  );
}
