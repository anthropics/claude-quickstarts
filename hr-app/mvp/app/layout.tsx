import type { Metadata } from "next";
import "./globals.css";
import { getDb } from "@/lib/db";
import { getSessionUser } from "@/lib/session";
import { unreadCount } from "@/lib/notify";
import NavLink from "@/components/NavLink";
import UserMenu from "@/components/UserMenu";
import NotificationBell from "@/components/NotificationBell";
import ImpersonationBanner from "@/components/ImpersonationBanner";

export const metadata: Metadata = {
  title: "HRCore",
  description: "HR platform — Core HR, Leave, Time, Payroll, ATS, Onboarding, Performance, Benefits, Expenses",
};

export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const user = getSessionUser();

  // Public surface (login, careers, kiosk) renders without app chrome;
  // middleware guarantees protected routes never reach here without a session.
  if (!user) {
    return (
      <html lang="en">
        <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">{children}</body>
      </html>
    );
  }

  const db = getDb();
  const unread = unreadCount(user.id);
  const impersonationTargets =
    user.role === "admin" || user.impersonated_by
      ? (db.prepare("SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status = 'active' ORDER BY first_name").all() as { id: number; name: string }[])
      : [];

  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        {user.impersonated_by && (
          <ImpersonationBanner name={`${user.first_name} ${user.last_name}`} />
        )}
        <div className="flex min-h-screen">
          <aside className="hidden w-60 shrink-0 border-r border-gray-200 bg-white p-4 md:flex md:flex-col">
            <div className="mb-6 flex items-center gap-2 px-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 font-bold text-white">H</div>
              <span className="text-lg font-bold">HRCore</span>
            </div>
            <nav className="flex flex-1 flex-col gap-1">
              <NavLink href="/" label="Dashboard" icon="home" />
              <p className="mt-3 mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-gray-400">People</p>
              <NavLink href="/employees" label="Employees" icon="people" />
              <NavLink href="/org-chart" label="Org Chart" icon="accountTree" />
              <p className="mt-3 mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-gray-400">Workforce</p>
              <NavLink href="/leave" label="Leave" icon="calendar" />
              <NavLink href="/time" label="Time & Attendance" icon="schedule" />
              <p className="mt-3 mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-gray-400">Talent</p>
              <NavLink href="/recruitment" label="Recruitment" icon="personSearch" />
              <NavLink href="/onboarding" label="Onboarding" icon="rocket" />
              <NavLink href="/performance" label="Performance" icon="barChart" />
              <p className="mt-3 mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-gray-400">Finance</p>
              <NavLink href="/payroll" label="Payroll" icon="payments" />
              <NavLink href="/expenses" label="Expenses" icon="receipt" />
              <NavLink href="/benefits" label="Benefits" icon="work" />
            </nav>
            <div className="mt-auto border-t border-gray-100 pt-3 text-xs text-gray-400">
              HRCore · v1.0
            </div>
          </aside>

          <div className="flex min-w-0 flex-1 flex-col">
            <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6 print:hidden">
              <div className="text-sm text-gray-500">Acme (Pty) Ltd</div>
              <div className="flex items-center gap-2">
                <NotificationBell initialUnread={unread} />
                <UserMenu
                  name={`${user.first_name} ${user.last_name}`}
                  role={user.role}
                  isAdmin={user.role === "admin" || user.impersonated_by !== null}
                  impersonating={user.impersonated_by !== null}
                  employees={impersonationTargets}
                />
              </div>
            </header>
            <main className="flex-1 p-6">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
