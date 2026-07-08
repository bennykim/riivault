import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep TypeScript type-checking enabled during builds (do not ignore).
  // Skip ESLint during builds per project convention.
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Pin the file-tracing root to this app (a stray lockfile lives above it).
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
