import type { Metadata } from "next";
import { Atkinson_Hyperlegible, Barlow_Condensed } from "next/font/google";
import "./globals.css";

const atkinson = Atkinson_Hyperlegible({
  weight: ["400", "700"],
  subsets: ["latin"],
  variable: "--font-atkinson",
  display: "swap",
});

const barlow = Barlow_Condensed({
  weight: ["600", "700"],
  subsets: ["latin"],
  variable: "--font-barlow",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Rastro · panel de demo",
  description:
    "Motor que sigue y cuenta en video sin duplicar. Meta hackathon — panel FRONT.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es" className={`${atkinson.variable} ${barlow.variable}`}>
      <body className="min-h-screen bg-ink text-[var(--text)] antialiased">
        {children}
      </body>
    </html>
  );
}
