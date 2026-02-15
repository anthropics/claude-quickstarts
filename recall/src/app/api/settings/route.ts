import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data } = await supabase
    .from("user_settings")
    .select("tmdb_api_key, spotify_access_token, youtube_access_token")
    .eq("user_id", user.id)
    .single();

  return NextResponse.json({
    tmdb_api_key: data?.tmdb_api_key ?? "",
    spotify_connected: !!data?.spotify_access_token,
    youtube_connected: !!data?.youtube_access_token,
  });
}

export async function PUT(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();

  const updates: Record<string, unknown> = {
    user_id: user.id,
    updated_at: new Date().toISOString(),
  };

  // TMDB key
  if (body.tmdb_api_key !== undefined) {
    const key = typeof body.tmdb_api_key === "string" ? body.tmdb_api_key.trim() : "";
    updates.tmdb_api_key = key || null;
  }

  // Spotify disconnect
  if (body.spotify_access_token === null) {
    updates.spotify_access_token = null;
    updates.spotify_refresh_token = null;
    updates.spotify_token_expires_at = null;
  }

  // YouTube disconnect
  if (body.youtube_access_token === null) {
    updates.youtube_access_token = null;
    updates.youtube_refresh_token = null;
    updates.youtube_token_expires_at = null;
  }

  const { error } = await supabase.from("user_settings").upsert(updates, {
    onConflict: "user_id",
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
