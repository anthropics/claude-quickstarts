import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const now = new Date();
  const currentYear = now.getFullYear();
  const yearStart = `${currentYear}-01-01T00:00:00.000Z`;

  // Fetch all entries for the user (needed for multiple calculations)
  const { data: allEntries, error } = await supabase
    .from("entries")
    .select("id, media_type, logged_at")
    .eq("user_id", user.id)
    .order("logged_at", { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const entries = allEntries ?? [];

  // total_count
  const total_count = entries.length;

  // year_count
  const year_count = entries.filter(
    (e) => e.logged_at >= yearStart
  ).length;

  // by_type
  const typeCounts = new Map<string, number>();
  for (const entry of entries) {
    typeCounts.set(
      entry.media_type,
      (typeCounts.get(entry.media_type) ?? 0) + 1
    );
  }
  const by_type = Array.from(typeCounts.entries()).map(
    ([media_type, count]) => ({
      media_type,
      count,
    })
  );

  // monthly: last 12 months
  const monthly: { month: string; count: number }[] = [];
  for (let i = 11; i >= 0; i--) {
    const d = new Date(currentYear, now.getMonth() - i, 1);
    const monthStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const count = entries.filter((e) => {
      const entryDate = new Date(e.logged_at);
      return (
        entryDate.getFullYear() === d.getFullYear() &&
        entryDate.getMonth() === d.getMonth()
      );
    }).length;
    monthly.push({ month: monthStr, count });
  }

  // on_this_day: entries from exactly one year ago (same month and day)
  const oneYearAgoMonth = now.getMonth();
  const oneYearAgoDay = now.getDate();
  const oneYearAgoYear = currentYear - 1;
  const on_this_day = entries.filter((e) => {
    const entryDate = new Date(e.logged_at);
    return (
      entryDate.getFullYear() === oneYearAgoYear &&
      entryDate.getMonth() === oneYearAgoMonth &&
      entryDate.getDate() === oneYearAgoDay
    );
  });

  // current_streak: consecutive days with at least 1 entry counting back from today
  const current_streak = calculateStreak(entries, now);

  return NextResponse.json({
    total_count,
    year_count,
    by_type,
    monthly,
    on_this_day,
    current_streak,
  });
}

function calculateStreak(
  entries: { logged_at: string }[],
  now: Date
): number {
  if (entries.length === 0) return 0;

  // Build a set of dates (YYYY-MM-DD) that have entries
  const datesWithEntries = new Set<string>();
  for (const entry of entries) {
    const d = new Date(entry.logged_at);
    const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    datesWithEntries.add(dateStr);
  }

  // Count consecutive days back from today
  let streak = 0;
  const checkDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  // Check if today has an entry; if not, start from yesterday
  const todayStr = formatDate(checkDate);
  if (!datesWithEntries.has(todayStr)) {
    checkDate.setDate(checkDate.getDate() - 1);
    const yesterdayStr = formatDate(checkDate);
    if (!datesWithEntries.has(yesterdayStr)) {
      return 0;
    }
  }

  while (true) {
    const dateStr = formatDate(checkDate);
    if (datesWithEntries.has(dateStr)) {
      streak++;
      checkDate.setDate(checkDate.getDate() - 1);
    } else {
      break;
    }
  }

  return streak;
}

function formatDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
