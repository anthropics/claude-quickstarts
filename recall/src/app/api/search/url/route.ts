import { NextRequest, NextResponse } from "next/server";
import type { SearchResult, MediaType } from "@/lib/types";

interface OEmbedResponse {
  title?: string;
  thumbnail_url?: string;
  author_name?: string;
}

export async function GET(request: NextRequest) {
  const url = request.nextUrl.searchParams.get("url");

  if (!url || url.trim().length === 0) {
    return NextResponse.json(
      { error: "Query parameter url is required" },
      { status: 400 }
    );
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(url);
  } catch {
    return NextResponse.json({ error: "Invalid URL" }, { status: 400 });
  }

  const hostname = parsedUrl.hostname.replace("www.", "");

  // YouTube
  if (hostname === "youtube.com" || hostname === "youtu.be") {
    return NextResponse.json(await extractYouTube(url));
  }

  // Spotify
  if (hostname === "open.spotify.com") {
    return NextResponse.json(await extractSpotify(url, parsedUrl));
  }

  // Unknown URL - return as article
  const fallback: SearchResult = {
    title: url,
    media_type: "article",
    thumbnail_url: null,
    source_api: "manual",
    source_api_id: null,
    author_or_creator: null,
    year: null,
    source_url: url,
  };

  return NextResponse.json(fallback);
}

async function extractYouTube(url: string): Promise<SearchResult> {
  const result: SearchResult = {
    title: url,
    media_type: "youtube",
    thumbnail_url: null,
    source_api: "youtube",
    source_api_id: extractYouTubeVideoId(url),
    author_or_creator: null,
    year: null,
    source_url: url,
  };

  try {
    const oembedUrl = `https://www.youtube.com/oembed?url=${encodeURIComponent(url)}&format=json`;
    const response = await fetch(oembedUrl);

    if (response.ok) {
      const data: OEmbedResponse = await response.json();
      result.title = data.title ?? url;
      result.thumbnail_url = data.thumbnail_url ?? null;
      result.author_or_creator = data.author_name ?? null;
    }
  } catch {
    // Fall through with defaults
  }

  return result;
}

function extractYouTubeVideoId(url: string): string | null {
  try {
    const parsed = new URL(url);
    const hostname = parsed.hostname.replace("www.", "");

    if (hostname === "youtu.be") {
      return parsed.pathname.slice(1) || null;
    }

    if (hostname === "youtube.com") {
      return parsed.searchParams.get("v");
    }
  } catch {
    // Invalid URL
  }

  return null;
}

async function extractSpotify(
  url: string,
  parsedUrl: URL
): Promise<SearchResult> {
  // Parse Spotify URL path: /track/ID, /album/ID, /episode/ID
  const pathParts = parsedUrl.pathname.split("/").filter(Boolean);
  const spotifyType = pathParts[0] ?? "track";
  const spotifyId = pathParts[1] ?? null;

  let mediaType: MediaType;
  switch (spotifyType) {
    case "album":
      mediaType = "album";
      break;
    case "episode":
      mediaType = "podcast";
      break;
    case "track":
    default:
      mediaType = "song";
      break;
  }

  const result: SearchResult = {
    title: url,
    media_type: mediaType,
    thumbnail_url: null,
    source_api: "spotify",
    source_api_id: spotifyId,
    author_or_creator: null,
    year: null,
    source_url: url,
  };

  try {
    const oembedUrl = `https://open.spotify.com/oembed?url=${encodeURIComponent(url)}`;
    const response = await fetch(oembedUrl);

    if (response.ok) {
      const data: OEmbedResponse = await response.json();
      result.title = data.title ?? url;
      result.thumbnail_url = data.thumbnail_url ?? null;
    }
  } catch {
    // Fall through with defaults
  }

  return result;
}
