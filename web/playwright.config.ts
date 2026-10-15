import { defineConfig, devices } from "@playwright/test";

// Tests run against the static export, served under the same base path as GitHub Pages
const PORT = 4173;
const URL = `http://localhost:${PORT}/sydney-travel-time/`;

export default defineConfig({
  testDir: "tests/e2e",
  use: { baseURL: URL },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npm run build && node scripts/serve.mjs out ${PORT}`,
    url: URL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
