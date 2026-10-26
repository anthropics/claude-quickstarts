import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

interface YouTubeHistoryItem {
  snippet: {
    title: string;
    description: string;
    thumbnails: {
      medium?: { url: string };
      default?: { url: string };
    };
    channelTitle: string;
    resourceId: { videoId: string };
  };
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
      "youtube_access_token, youtube_refresh_token, youtube_token_expires_at"
    )
    .eq("user_id", user.id)
    .single();

  if (!settings?.youtube_access_token) {
    return NextResponse.json({ error: "YouTube not connected" }, { status: 404 });
  }

  let accessToken = settings.youtube_access_token;

  // Refresh token if expired
  if (
    settings.youtube_token_expires_at &&
    new Date(settings.youtube_token_expires_at) <= new Date()
  ) {
    const clientId = process.env.NEXT_PUBLIC_YOUTUBE_CLIENT_ID;
    if (!clientId || !settings.youtube_refresh_token) {
      return NextResponse.json(
        { error: "Cannot refresh token" },
        { status: 401 }
      );
    }

    const refreshRes = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: clientId,
        grant_type: "refresh_token",
        refresh_token: settings.youtube_refresh_token,
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

    await supabase
      .from("user_settings")
      .update({
        youtube_access_token: refreshData.access_token,
        youtube_refresh_token:
          refreshData.refresh_token || settings.youtube_refresh_token,
        youtube_token_expires_at: new Date(
          Date.now() + refreshData.expires_in * 1000
        ).toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("user_id", user.id);
  }

  // Fetch watch history via YouTube Data API
  // Note: This requires the user's watch history to be accessible
  const res = await fetch(
    "https://www.googleapis.com/youtube/v3/activities?part=snippet&mine=true&maxResults=20",
    {
      headers: { Authorization: `Bearer ${accessToken}` },
    }
  );

  if (!res.ok) {
    return NextResponse.json(
      { error: "Failed to fetch YouTube history" },
      { status: res.status }
    );
  }

  const data = await res.json();
  const items = (data.items ?? []) as YouTubeHistoryItem[];

  const results = items
    .filter((item) => item.snippet?.resourceId?.videoId)
    .map((item) => ({
      id: item.snippet.resourceId.videoId,
      title: item.snippet.title,
      channel: item.snippet.channelTitle,
      thumbnail_url:
        item.snippet.thumbnails?.medium?.url ||
        item.snippet.thumbnails?.default?.url ||
        null,
      source_url: `https://www.youtube.com/watch?v=${item.snippet.resourceId.videoId}`,
    }));

  return NextResponse.json(results);
}
