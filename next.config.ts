import type { NextConfig } from "next";

const apiUrl = process.env.SLICE_STUDIO_API_URL || "http://127.0.0.1:4110";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl.replace(/\/+$/, "")}/api/:path*`
      }
    ];
  }
};

export default nextConfig;
