import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },
  // Cho phép truy cập từ Cloudflare Tunnel khi dev
  allowedDevOrigins: [
    'https://referrals-walnut-rotation-allow.trycloudflare.com',
  ],
  devIndicators: false,
  // Tăng giới hạn body để cho phép upload video lớn qua proxy
  experimental: {
    serverActions: {
      bodySizeLimit: '500mb',
    },
  },
  // Cho phép middleware/proxy xử lý body lớn
  serverExternalPackages: [],
  async rewrites() {
    return [
      {
        // Proxy API requests to the FastAPI backend
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
      {
        // Proxy static assets (e.g., snapshots) to the FastAPI backend
        source: '/static/:path*',
        destination: 'http://localhost:8000/static/:path*',
      },
    ];
  },
};

export default nextConfig;
