import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Road trip planner - Claude Managed Agents",
  description:
    "A national-park trip-planning chat where the model is a Claude Managed Agent session: token streaming over the session event stream, and vendor API keys the model never holds.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
