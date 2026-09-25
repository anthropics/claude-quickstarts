"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import { Plus, Music, Youtube, Loader2, Check } from "lucide-react";
import { toast } from "sonner";

interface SpotifyTrack {
  id: string;
  title: string;
  artist: string;
  album: string;
  thumbnail_url: string | null;
  source_url: string;
}

interface YouTubeVideo {
  id: string;
  title: string;
  channel: string;
  thumbnail_url: string | null;
  source_url: string;
}

interface RecentlyConsumedProps {
  onEntryCreated: () => void;
}

export function RecentlyConsumed({ onEntryCreated }: RecentlyConsumedProps) {
  const [spotifyTracks, setSpotifyTracks] = useState<SpotifyTrack[]>([]);
  const [youtubeTracks, setYoutubeTracks] = useState<YouTubeVideo[]>([]);
  const [spotifyConnected, setSpotifyConnected] = useState(false);
  const [youtubeConnected, setYoutubeConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loggingId, setLoggingId] = useState<string | null>(null);

  const fetchRecent = useCallback(async () => {
    setLoading(true);

    const [spotifyRes, youtubeRes] = await Promise.allSettled([
      fetch("/api/spotify/recently-played"),
      fetch("/api/youtube/recently-watched"),
    ]);

    if (spotifyRes.status === "fulfilled" && spotifyRes.value.ok) {
      const data = await spotifyRes.value.json();
      setSpotifyTracks(data);
      setSpotifyConnected(true);
    } else if (
      spotifyRes.status === "fulfilled" &&
      spotifyRes.value.status !== 404
    ) {
      // 404 means not connected, which is fine
      setSpotifyConnected(false);
    }

    if (youtubeRes.status === "fulfilled" && youtubeRes.value.ok) {
      const data = await youtubeRes.value.json();
      setYoutubeTracks(data);
      setYoutubeConnected(true);
    } else if (
      youtubeRes.status === "fulfilled" &&
      youtubeRes.value.status !== 404
    ) {
      setYoutubeConnected(false);
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    fetchRecent();
  }, [fetchRecent]);

  // Refresh on window focus
  useEffect(() => {
    function handleFocus() {
      fetchRecent();
    }
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [fetchRecent]);

  const handleLogSpotify = async (track: SpotifyTrack) => {
    setLoggingId(track.id);
    try {
      const res = await fetch("/api/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: track.title,
          media_type: "song",
          thumbnail_url: track.thumbnail_url,
          note: null,
          rating: null,
          source_url: track.source_url,
          source_api: "spotify",
          source_api_id: track.id,
          author_or_creator: track.artist,
          year: null,
        }),
      });
      if (res.ok) {
        toast.success("Logged!", {
          icon: <Check size={16} className="text-green-400" />,
          duration: 2000,
        });
        onEntryCreated();
      }
    } catch {
      toast.error("Failed to log.");
    } finally {
      setLoggingId(null);
    }
  };

  const handleLogYoutube = async (video: YouTubeVideo) => {
    setLoggingId(video.id);
    try {
      const res = await fetch("/api/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: video.title,
          media_type: "youtube",
          thumbnail_url: video.thumbnail_url,
          note: null,
          rating: null,
          source_url: video.source_url,
          source_api: "youtube",
          source_api_id: video.id,
          author_or_creator: video.channel,
          year: null,
        }),
      });
      if (res.ok) {
        toast.success("Logged!", {
          icon: <Check size={16} className="text-green-400" />,
          duration: 2000,
        });
        onEntryCreated();
      }
    } catch {
      toast.error("Failed to log.");
    } finally {
      setLoggingId(null);
    }
  };

  if (loading) return null;
  if (!spotifyConnected && !youtubeConnected) return null;
  if (spotifyTracks.length === 0 && youtubeTracks.length === 0) return null;

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-foreground-muted uppercase tracking-wider">
        Recently consumed
      </h3>

      {/* Spotify tracks */}
      {spotifyTracks.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Music size={14} className="text-[#1DB954]" />
            <span className="text-xs text-foreground-subtle">Spotify</span>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
            {spotifyTracks.slice(0, 10).map((track) => (
              <div
                key={track.id}
                className="flex-shrink-0 w-28 group relative"
              >
                <div className="relative">
                  {track.thumbnail_url ? (
                    <Image
                      src={track.thumbnail_url}
                      alt={track.title}
                      width={112}
                      height={112}
                      className="w-28 h-28 rounded-lg object-cover"
                    />
                  ) : (
                    <div className="w-28 h-28 rounded-lg bg-background-elevated flex items-center justify-center">
                      <Music size={24} className="text-foreground-subtle" />
                    </div>
                  )}
                  <button
                    onClick={() => handleLogSpotify(track)}
                    disabled={loggingId !== null}
                    className="absolute inset-0 flex items-center justify-center rounded-lg bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    {loggingId === track.id ? (
                      <Loader2
                        size={20}
                        className="text-white animate-spin"
                      />
                    ) : (
                      <Plus size={24} className="text-white" />
                    )}
                  </button>
                </div>
                <p className="text-xs font-medium mt-1.5 truncate">
                  {track.title}
                </p>
                <p className="text-xs text-foreground-subtle truncate">
                  {track.artist}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* YouTube videos */}
      {youtubeTracks.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Youtube size={14} className="text-[#f97316]" />
            <span className="text-xs text-foreground-subtle">YouTube</span>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
            {youtubeTracks.slice(0, 10).map((video) => (
              <div
                key={video.id}
                className="flex-shrink-0 w-40 group relative"
              >
                <div className="relative">
                  {video.thumbnail_url ? (
                    <Image
                      src={video.thumbnail_url}
                      alt={video.title}
                      width={160}
                      height={90}
                      className="w-40 h-[90px] rounded-lg object-cover"
                    />
                  ) : (
                    <div className="w-40 h-[90px] rounded-lg bg-background-elevated flex items-center justify-center">
                      <Youtube size={24} className="text-foreground-subtle" />
                    </div>
                  )}
                  <button
                    onClick={() => handleLogYoutube(video)}
                    disabled={loggingId !== null}
                    className="absolute inset-0 flex items-center justify-center rounded-lg bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    {loggingId === video.id ? (
                      <Loader2
                        size={20}
                        className="text-white animate-spin"
                      />
                    ) : (
                      <Plus size={24} className="text-white" />
                    )}
                  </button>
                </div>
                <p className="text-xs font-medium mt-1.5 truncate">
                  {video.title}
                </p>
                <p className="text-xs text-foreground-subtle truncate">
                  {video.channel}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
