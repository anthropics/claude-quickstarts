import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function POST(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { code, code_verifier, redirect_uri } = await request.json();

  if (!code || !code_verifier || !redirect_uri) {
    return NextResponse.json(
      { error: "Missing required fields" },
      { status: 400 }
    );
  }

  const clientId = process.env.NEXT_PUBLIC_YOUTUBE_CLIENT_ID;
  if (!clientId) {
    return NextResponse.json(
      { error: "YouTube client ID not configured" },
      { status: 500 }
    );
  }

  // Exchange authorization code for tokens
  const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: clientId,
      grant_type: "authorization_code",
      code,
      redirect_uri,
      code_verifier,
    }),
  });

  if (!tokenRes.ok) {
    const err = await tokenRes.text();
    return NextResponse.json(
      { error: "Token exchange failed", details: err },
      { status: 400 }
    );
  }

  const tokens = await tokenRes.json();
  const expiresAt = new Date(
    Date.now() + tokens.expires_in * 1000
  ).toISOString();

  // Store tokens
  const { error } = await supabase.from("user_settings").upsert(
    {
      user_id: user.id,
      youtube_access_token: tokens.access_token,
      youtube_refresh_token: tokens.refresh_token,
      youtube_token_expires_at: expiresAt,
      updated_at: new Date().toISOString(),
    },
    { onConflict: "user_id" }
  );

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
