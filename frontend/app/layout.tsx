import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GulzarSoft Research Console",
  description: "Professional AI research chat interface for your multi-agent backend.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
