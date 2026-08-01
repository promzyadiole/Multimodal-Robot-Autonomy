import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Hides the floating "N" dev-tools badge. Build and runtime errors are still
  // surfaced; only the on-screen route indicator goes away.
  devIndicators: false,
};

export default nextConfig;
