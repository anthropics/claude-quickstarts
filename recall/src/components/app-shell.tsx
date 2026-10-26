"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { User } from "@supabase/supabase-js";
import {
  Home,
  Search,
  BarChart3,
  Settings,
  Plus,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Timeline", icon: Home },
  { href: "/search", label: "Search", icon: Search },
  { href: "/stats", label: "Stats", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({
  children,
}: {
  user: User;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [fabPulse, setFabPulse] = useState(false);

  const scrollToSearchBar = () => {
    setFabPulse(true);
    setTimeout(() => setFabPulse(false), 300);

    // Scroll to top and focus the search input
    window.scrollTo({ top: 0, behavior: "smooth" });
    setTimeout(() => {
      const input = document.querySelector<HTMLInputElement>(
        'input[placeholder*="What did you"]'
      );
      if (input) {
        input.focus();
      }
    }, 400);
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top header */}
      <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight font-serif text-primary">
              Recall
            </h1>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden items-center gap-1 md:flex">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-foreground-muted hover:text-foreground hover:bg-background-elevated"
                  }`}
                >
                  <Icon size={16} />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6 pb-24 md:pb-6">
        {children}
      </main>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/90 backdrop-blur-md md:hidden">
        <div className="mx-auto flex max-w-3xl items-center justify-around py-2">
          {NAV_ITEMS.slice(0, 2).map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center gap-1 rounded-lg px-4 py-1.5 text-xs transition-colors ${
                  isActive
                    ? "text-primary"
                    : "text-foreground-subtle hover:text-foreground-muted"
                }`}
              >
                <Icon size={20} />
                {item.label}
              </Link>
            );
          })}

          {/* FAB placeholder space */}
          <div className="w-14" />

          {NAV_ITEMS.slice(2).map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center gap-1 rounded-lg px-4 py-1.5 text-xs transition-colors ${
                  isActive
                    ? "text-primary"
                    : "text-foreground-subtle hover:text-foreground-muted"
                }`}
              >
                <Icon size={20} />
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Floating Action Button - mobile only */}
      <button
        onClick={scrollToSearchBar}
        className={`fixed bottom-8 left-1/2 -translate-x-1/2 z-[60] md:hidden flex h-14 w-14 items-center justify-center rounded-full bg-primary text-white shadow-lg shadow-primary/30 transition-transform active:scale-90 ${
          fabPulse ? "scale-110" : "scale-100"
        }`}
        aria-label="Log something"
      >
        <Plus size={24} />
      </button>
    </div>
  );
}
