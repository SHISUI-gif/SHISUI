import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // localhost以外(127.0.0.1・LAN IP)からのアクセス時に開発用HMRリソースが
  // ブロックされる警告が出ていたため、明示的に許可しておく
  allowedDevOrigins: ["127.0.0.1", "localhost", "192.168.0.53"],
  // ブラウザからは常に同一オリジンの/api/*だけを叩かせ、Next.jsサーバー側で
  // このMac上のFastAPI(127.0.0.1:8000)へ転送する。これにより、LANのIPでも
  // 外部トンネル経由でも、ポート3000を1つ公開するだけで済む(CORSも不要になる)。
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ]
  },
};

export default nextConfig;
