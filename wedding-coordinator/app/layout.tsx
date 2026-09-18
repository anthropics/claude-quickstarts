import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Svatební koordinátorka | Claude Quickstart",
  description:
    "Elitní VIP svatební koordinátorka poháněná Claude — rozpočet, harmonogram a komunikace s dodavateli na jednom místě.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="cs">
      <body className="bg-ink text-ivory antialiased">{children}</body>
    </html>
  );
}
