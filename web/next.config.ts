import type { NextConfig } from "next";

// GitHub Pages serves this project site from /sydney-travel-time/
const basePath = process.env.BASE_PATH ?? "/sydney-travel-time";

const config: NextConfig = {
  output: "export",
  basePath,
  trailingSlash: true,
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};

export default config;
