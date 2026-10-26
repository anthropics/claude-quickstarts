import KioskClient from "./KioskClient";

export const metadata = { title: "Clock kiosk — HRCore" };
export const dynamic = "force-dynamic";

/**
 * Public kiosk terminal (PIN-authenticated per action). Renders its own
 * fullscreen chrome — the root layout is bare for session-less requests, and
 * the fixed overlay also covers the app shell if a signed-in user opens it.
 */
export default function KioskPage() {
  return <KioskClient />;
}
