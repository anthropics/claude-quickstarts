import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

interface SpotifyTrack {
  track: {
    id: string;
    name: string;
    album: {
      name: string;
      images: { url: string; width: number }[];
    };
    artists: { name: string }[];
    external_urls: { spotify: string };
    type: string;
  };
  played_at: string;
}

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data: settings } = await supabase
    .from("user_settings")
    .select(
      "spotify_access_token, spotify_refresh_token, spotify_token_expires_at"
    )
    .eq("user_id", user.id)
    .single();

  if (!settings?.spotify_access_token) {
    return NextResponse.json({ error: "Spotify not connected" }, { status: 404 });
  }

  let accessToken = settings.spotify_access_token;

  // Refresh token if expired
  if (
    settings.spotify_token_expires_at &&
    new Date(settings.spotify_token_expires_at) <= new Date()
  ) {
    const clientId = process.env.NEXT_PUBLIC_SPOTIFY_CLIENT_ID;
    if (!clientId || !settings.spotify_refresh_token) {
      return NextResponse.json(
        { error: "Cannot refresh token" },
        { status: 401 }
      );
    }

    const refreshRes = await fetch("https://accounts.spotify.com/api/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: clientId,
        grant_type: "refresh_token",
        refresh_token: settings.spotify_refresh_token,
      }),
    });

    if (!refreshRes.ok) {
      return NextResponse.json(
        { error: "Token refresh failed" },
        { status: 401 }
      );
    }

    const refreshData = await refreshRes.json();
    accessToken = refreshData.access_token;

    // Update stored tokens
    await supabase
      .from("user_settings")
      .update({
        spotify_access_token: refreshData.access_token,
        spotify_refresh_token:
          refreshData.refresh_token || settings.spotify_refresh_token,
        spotify_token_expires_at: new Date(
          Date.now() + refreshData.expires_in * 1000
        ).toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("user_id", user.id);
  }

  // Fetch recently played
  const res = await fetch(
    "https://api.spotify.com/v1/me/player/recently-played?limit=20",
    {
      headers: { Authorization: `Bearer ${accessToken}` },
    }
  );

  if (!res.ok) {
    return NextResponse.json(
      { error: "Failed to fetch recently played" },
      { status: res.status }
    );
  }

  const data = await res.json();
  const items = (data.items ?? []) as SpotifyTrack[];

  // Deduplicate by track ID (keep the most recent play)
  const seen = new Set<string>();
  const results = items
    .filter((item) => {
      if (seen.has(item.track.id)) return false;
      seen.add(item.track.id);
      return true;
    })
    .map((item) => ({
      id: item.track.id,
      title: item.track.name,
      artist: item.track.artists.map((a) => a.name).join(", "),
      album: item.track.album.name,
      thumbnail_url:
        item.track.album.images.find((i) => i.width <= 300)?.url ||
        item.track.album.images[0]?.url ||
        null,
      source_url: item.track.external_urls.spotify,
      played_at: item.played_at,
    }));

  return NextResponse.json(results);
}
