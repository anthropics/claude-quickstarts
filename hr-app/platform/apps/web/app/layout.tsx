import type { ReactNode } from "react";

export const metadata = {
  title: "HRCore",
  description: "HRCore production platform",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
