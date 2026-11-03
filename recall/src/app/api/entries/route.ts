import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import type { MediaType } from "@/lib/types";

export async function GET(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const searchParams = request.nextUrl.searchParams;
  const type = searchParams.get("type") as MediaType | null;
  const q = searchParams.get("q");
  const from = searchParams.get("from");
  const to = searchParams.get("to");
  const rating = searchParams.get("rating");

  let query = supabase
    .from("entries")
    .select("*")
    .eq("user_id", user.id)
    .order("logged_at", { ascending: false })
    .limit(50);

  if (type) {
    query = query.eq("media_type", type);
  }

  if (q) {
    query = query.or(`title.ilike.%${q}%,note.ilike.%${q}%`);
  }

  if (from) {
    query = query.gte("logged_at", from);
  }

  if (to) {
    query = query.lte("logged_at", to);
  }

  if (rating) {
    query = query.eq("rating", parseInt(rating, 10));
  }

  const { data, error } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}

export async function POST(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await request.json();

  const {
    title,
    media_type,
    thumbnail_url,
    note,
    rating,
    source_url,
    source_api,
    source_api_id,
    author_or_creator,
    year,
  } = body;

  if (!title || !media_type) {
    return NextResponse.json(
      { error: "title and media_type are required" },
      { status: 400 }
    );
  }

  const { data, error } = await supabase
    .from("entries")
    .insert({
      user_id: user.id,
      title,
      media_type,
      thumbnail_url: thumbnail_url ?? null,
      note: note ?? null,
      rating: rating ?? null,
      source_url: source_url ?? null,
      source_api: source_api ?? null,
      source_api_id: source_api_id ?? null,
      author_or_creator: author_or_creator ?? null,
      year: year ?? null,
      logged_at: new Date().toISOString(),
    })
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data, { status: 201 });
}
