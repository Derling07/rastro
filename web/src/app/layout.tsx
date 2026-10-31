import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Mono, Source_Sans_3 } from "next/font/google";
import "./globals.css";

const source = Source_Sans_3({
  weight: ["400", "600", "700"],
  subsets: ["latin"],
  variable: "--font-source",
  display: "swap",
});

const plex = IBM_Plex_Mono({
  weight: ["400", "600"],
  subsets: ["latin"],
  variable: "--font-plex",
  display: "swap",
});

const fraunces = Fraunces({
  weight: ["500", "600", "700"],
  subsets: ["latin"],
  variable: "--font-note",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Rastro",
  description:
    "Count each individual once, then ask a person before the alert leaves the notebook. SAM 3.1 tracks the frame. Muse Spark writes the field note.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${source.variable} ${plex.variable} ${fraunces.variable}`}>
      <body className="min-h-screen bg-paper text-[var(--text)] antialiased">
        {children}
      </body>
    </html>
  );
}
