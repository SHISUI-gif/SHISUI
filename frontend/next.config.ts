import type { NextConfig } from "next";

// クラウド移行(Vercel+Oracle Cloud VM)後は、BACKEND_URL環境変数でFastAPIの
// 公開URLを指すよう切り替えられるようにする(docs/deploy_oracle.md参照)。
// 未設定時はこれまで通りこのMac上のローカルFastAPIを指す(既存の挙動を維持)。
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // localhost以外(127.0.0.1・LAN IP)からのアクセス時に開発用HMRリソースが
  // ブロックされる警告が出ていたため、明示的に許可しておく
  allowedDevOrigins: ["127.0.0.1", "localhost", "192.168.0.53"],
  // ブラウザからは常に同一オリジンの/api/*だけを叩かせ、Next.jsサーバー側で
  // FastAPI(BACKEND_URL)へ転送する。これにより、LANのIPでも外部トンネル経由でも、
  // ポート1つを公開するだけで済む(CORSも不要になる)。
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ]
  },
};

export default nextConfig;
