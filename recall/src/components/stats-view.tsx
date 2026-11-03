"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  Flame,
  Calendar,
  TrendingUp,
  Star,
  Lightbulb,
  CalendarDays,
} from "lucide-react";
import { MEDIA_TYPE_CONFIG, MediaType, Entry } from "@/lib/types";
import { MediaTypeBadge } from "@/components/media-type-badge";
import { format } from "date-fns";

interface Stats {
  total_count: number;
  year_count: number;
  month_count: number;
  by_type: { media_type: MediaType; count: number }[];
  monthly: { month: string; count: number }[];
  on_this_day: Entry[];
  current_streak: number;
  top_rated: { id: string; title: string; media_type: MediaType; rating: number }[];
  insights: string[];
}

export function StatsView() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const res = await fetch("/api/stats");
        if (res.ok) {
          const data = await res.json();
          setStats(data);
        }
      } catch {
        // Handle error silently
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-semibold font-serif">Stats</h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="rounded-xl bg-background-card border border-border-subtle p-4 animate-pulse"
            >
              <div className="h-8 w-16 rounded bg-background-elevated mb-2" />
              <div className="h-3 w-20 rounded bg-background-elevated" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="text-center py-12">
        <p className="text-foreground-muted">Could not load stats</p>
      </div>
    );
  }

  const pieColors = stats.by_type.map(
    (item) => MEDIA_TYPE_CONFIG[item.media_type]?.color || "#6b7280"
  );

  const monthlyData = stats.monthly.map((m) => ({
    ...m,
    label: format(new Date(m.month + "-01"), "MMM"),
  }));

  return (
    <div className="space-y-8 pb-20">
      <div>
        <h2 className="text-2xl font-semibold font-serif mb-1">Stats</h2>
        <p className="text-foreground-muted text-sm">
          Your media consumption at a glance
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard
          icon={<TrendingUp size={18} />}
          value={stats.total_count}
          label="All time"
        />
        <StatCard
          icon={<Calendar size={18} />}
          value={stats.year_count}
          label="This year"
        />
        <StatCard
          icon={<CalendarDays size={18} />}
          value={stats.month_count}
          label="This month"
        />
        <StatCard
          icon={<Flame size={18} />}
          value={stats.current_streak}
          label="Day streak"
        />
      </div>

      {/* Insights */}
      {stats.insights.length > 0 && (
        <section className="space-y-2">
          {stats.insights.map((insight, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3 rounded-xl bg-background-card border border-border-subtle p-4"
            >
              <Lightbulb size={16} className="text-primary flex-shrink-0 mt-0.5" />
              <p className="text-sm text-foreground-muted">{insight}</p>
            </div>
          ))}
        </section>
      )}

      {/* Type breakdown */}
      {stats.by_type.length > 0 && (
        <section className="rounded-xl bg-background-card border border-border-subtle p-5">
          <h3 className="font-serif font-semibold mb-4">By Type</h3>
          <div className="flex flex-col md:flex-row gap-6 items-center">
            <div className="w-48 h-48">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={stats.by_type}
                    dataKey="count"
                    nameKey="media_type"
                    cx="50%"
                    cy="50%"
                    innerRadius={35}
                    outerRadius={70}
                    strokeWidth={2}
                    stroke="#1a1a2e"
                  >
                    {stats.by_type.map((_, index) => (
                      <Cell key={index} fill={pieColors[index]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "#222244",
                      border: "1px solid #3a3860",
                      borderRadius: "8px",
                      color: "#e8e6f0",
                      fontSize: "13px",
                    }}
                    formatter={(value, name) => [
                      value,
                      MEDIA_TYPE_CONFIG[name as MediaType]?.label || name,
                    ]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 grid grid-cols-2 gap-2">
              {stats.by_type.map((item) => (
                <div
                  key={item.media_type}
                  className="flex items-center justify-between gap-2 rounded-lg bg-background-elevated px-3 py-2"
                >
                  <MediaTypeBadge type={item.media_type} size="sm" />
                  <span className="text-sm font-medium">{item.count}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Monthly activity */}
      {monthlyData.length > 0 && (
        <section className="rounded-xl bg-background-card border border-border-subtle p-5">
          <h3 className="font-serif font-semibold mb-4">Monthly Activity</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyData}>
                <XAxis
                  dataKey="label"
                  tick={{ fill: "#9896a8", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "#9896a8", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "#222244",
                    border: "1px solid #3a3860",
                    borderRadius: "8px",
                    color: "#e8e6f0",
                    fontSize: "13px",
                  }}
                  formatter={(value) => [value, "Entries"]}
                />
                <Bar
                  dataKey="count"
                  fill="#c9a052"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={40}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Top rated */}
      {stats.top_rated.length > 0 && (
        <section className="rounded-xl bg-background-card border border-border-subtle p-5">
          <h3 className="font-serif font-semibold mb-4 flex items-center gap-2">
            <Star size={16} className="text-primary" />
            Top Rated
          </h3>
          <div className="space-y-2">
            {stats.top_rated.map((entry) => (
              <div
                key={entry.id}
                className="flex items-center gap-3 rounded-lg bg-background-elevated px-3 py-2"
              >
                <div className="flex-1 min-w-0">
                  <p className="font-serif text-sm font-medium truncate">
                    {entry.title}
                  </p>
                </div>
                <MediaTypeBadge type={entry.media_type} size="sm" />
                <div className="flex gap-0.5">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <Star
                      key={s}
                      size={12}
                      className="fill-primary text-primary"
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* On this day */}
      {stats.on_this_day.length > 0 && (
        <section className="rounded-xl bg-background-card border border-border-subtle p-5">
          <h3 className="font-serif font-semibold mb-4">
            On This Day (1 Year Ago)
          </h3>
          <div className="space-y-2">
            {stats.on_this_day.map((entry) => (
              <div
                key={entry.id}
                className="flex items-center gap-3 rounded-lg bg-background-elevated p-3"
              >
                {entry.thumbnail_url ? (
                  <Image
                    src={entry.thumbnail_url}
                    alt={entry.title}
                    width={36}
                    height={48}
                    className="h-12 w-9 rounded object-cover flex-shrink-0"
                  />
                ) : (
                  <div className="h-12 w-9 rounded bg-background flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="font-serif font-medium text-sm truncate">
                    {entry.title}
                  </p>
                  <MediaTypeBadge type={entry.media_type} size="sm" />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function StatCard({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode;
  value: number;
  label: string;
}) {
  return (
    <div className="rounded-xl bg-background-card border border-border-subtle p-4">
      <div className="flex items-center gap-2 text-primary mb-1">{icon}</div>
      <p className="text-2xl font-semibold font-serif">{value}</p>
      <p className="text-xs text-foreground-muted">{label}</p>
    </div>
  );
}
