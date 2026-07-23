import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Orbitron, Syne } from "next/font/google";
import { GrainOverlay } from "@/components/GrainOverlay";
import "./globals.css";

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const syne = Syne({
  variable: "--font-syne",
  subsets: ["latin"],
  weight: ["700", "800"],
});

// ホームの見出し用。当初はドットマトリクス風(DotGothic16)にしていたが、
// レトロ・可愛い方向に寄りすぎて「かっこよさ」が足りないとの指摘を受け、
// 幾何学的でSF/サイバー感の強いOrbitronに変更した。
const orbitron = Orbitron({
  variable: "--font-orbitron",
  subsets: ["latin"],
  weight: ["700", "900"],
});

export const metadata: Metadata = {
  title: "志粋 — SHISUI",
  description: "自律型ローカルAIアシスタント「志粋」",
  // iPhoneで「ホーム画面に追加」した際、Safariのアドレスバー無しの
  // フルスクリーンアプリとして開かせるための設定
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "志粋",
  },
  icons: {
    icon: [
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#000000",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ja"
      className={`${plexMono.variable} ${syne.variable} ${orbitron.variable} dark h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-black text-white">
        <GrainOverlay />
        {children}
      </body>
    </html>
  );
}
