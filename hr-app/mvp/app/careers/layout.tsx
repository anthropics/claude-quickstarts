import type { Metadata } from "next";
import Link from "next/link";
import { getSessionUser } from "@/lib/session";

export const metadata: Metadata = {
  title: "Careers — Acme (Pty) Ltd",
  description: "Open positions at Acme (Pty) Ltd",
};

export const dynamic = "force-dynamic";

/**
 * Public careers chrome. The root layout renders bare children when there is
 * no session, so this layout carries its own minimal branding. When a signed-in
 * user browses careers, the app sidebar is already present, so the header
 * strip is skipped to avoid double chrome.
 */
export default function CareersLayout({ children }: { children: React.ReactNode }) {
  const user = getSessionUser();

  if (user) {
    return <div className="mx-auto max-w-3xl">{children}</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link href="/careers" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 font-bold text-white">
              A
            </span>
            <span className="text-lg font-bold">Acme (Pty) Ltd</span>
            <span className="ml-1 text-sm font-medium text-gray-400">Careers</span>
          </Link>
          <span className="text-xs text-gray-400">Powered by HRCore</span>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10">{children}</main>
      <footer className="mx-auto max-w-3xl px-4 pb-10 text-center text-xs text-gray-400">
        © {new Date().getFullYear()} Acme (Pty) Ltd · All applications are treated confidentially.
      </footer>
    </div>
  );
}
