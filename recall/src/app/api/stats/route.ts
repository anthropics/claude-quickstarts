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
  const currentMonth = now.getMonth();
  const yearStart = `${currentYear}-01-01T00:00:00.000Z`;

  // Fetch all entries for the user
  const { data: allEntries, error } = await supabase
    .from("entries")
    .select("id, media_type, logged_at, rating, title")
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

  // month_count
  const monthStart = new Date(currentYear, currentMonth, 1).toISOString();
  const month_count = entries.filter(
    (e) => e.logged_at >= monthStart
  ).length;

  // by_type
  const typeCounts = new Map<string, number>();
  for (const entry of entries) {
    typeCounts.set(
      entry.media_type,
      (typeCounts.get(entry.media_type) ?? 0) + 1
    );
  }
  const by_type = Array.from(typeCounts.entries())
    .map(([media_type, count]) => ({ media_type, count }))
    .sort((a, b) => b.count - a.count);

  // monthly: last 12 months
  const monthly: { month: string; count: number }[] = [];
  for (let i = 11; i >= 0; i--) {
    const d = new Date(currentYear, currentMonth - i, 1);
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

  // on_this_day: entries from exactly one year ago
  const oneYearAgoMonth = currentMonth;
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

  // current_streak
  const current_streak = calculateStreak(entries, now);

  // top_rated: entries with 5-star ratings
  const top_rated = entries
    .filter((e) => e.rating === 5)
    .slice(0, 10);

  // Insights / pattern observations
  const insights: string[] = [];

  // Month-over-month comparison
  const thisMonthCount = monthly[monthly.length - 1]?.count ?? 0;
  const lastMonthCount = monthly[monthly.length - 2]?.count ?? 0;
  if (thisMonthCount > 0 || lastMonthCount > 0) {
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const thisMonthName = monthNames[currentMonth];

    if (thisMonthCount > lastMonthCount) {
      insights.push(
        `You've logged ${thisMonthCount} item${thisMonthCount !== 1 ? "s" : ""} in ${thisMonthName} — up from ${lastMonthCount} last month`
      );
    } else if (thisMonthCount < lastMonthCount) {
      insights.push(
        `You've logged ${thisMonthCount} item${thisMonthCount !== 1 ? "s" : ""} in ${thisMonthName} — down from ${lastMonthCount} last month`
      );
    } else if (thisMonthCount > 0) {
      insights.push(
        `You've logged ${thisMonthCount} item${thisMonthCount !== 1 ? "s" : ""} in ${thisMonthName} — same as last month`
      );
    }
  }

  // Most active day of the week
  if (entries.length >= 7) {
    const dayCounts = [0, 0, 0, 0, 0, 0, 0]; // Sun-Sat
    for (const entry of entries) {
      const day = new Date(entry.logged_at).getDay();
      dayCounts[day]++;
    }
    const maxDay = dayCounts.indexOf(Math.max(...dayCounts));
    const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    insights.push(`Your most active day is ${dayNames[maxDay]}`);
  }

  // Media type gaps (haven't logged X in N weeks)
  const typeLastLogged = new Map<string, Date>();
  for (const entry of entries) {
    const existing = typeLastLogged.get(entry.media_type);
    const entryDate = new Date(entry.logged_at);
    if (!existing || entryDate > existing) {
      typeLastLogged.set(entry.media_type, entryDate);
    }
  }

  const threeWeeksAgo = new Date(now.getTime() - 21 * 24 * 60 * 60 * 1000);
  const typeLabels: Record<string, string> = {
    book: "books",
    film: "films",
    tv_series: "TV shows",
    podcast: "podcasts",
    album: "albums",
    song: "music",
    youtube: "YouTube videos",
    article: "articles",
  };

  for (const [type, lastDate] of typeLastLogged.entries()) {
    if (lastDate < threeWeeksAgo && typeLabels[type]) {
      const weeksDiff = Math.floor(
        (now.getTime() - lastDate.getTime()) / (7 * 24 * 60 * 60 * 1000)
      );
      insights.push(
        `You haven't logged any ${typeLabels[type]} in ${weeksDiff} week${weeksDiff !== 1 ? "s" : ""}`
      );
    }
  }

  return NextResponse.json({
    total_count,
    year_count,
    month_count,
    by_type,
    monthly,
    on_this_day,
    current_streak,
    top_rated,
    insights,
  });
}

function calculateStreak(
  entries: { logged_at: string }[],
  now: Date
): number {
  if (entries.length === 0) return 0;

  const datesWithEntries = new Set<string>();
  for (const entry of entries) {
    const d = new Date(entry.logged_at);
    const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    datesWithEntries.add(dateStr);
  }

  let streak = 0;
  const checkDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());

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
