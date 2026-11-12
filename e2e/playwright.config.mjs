import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export default defineConfig({
  testDir: ".",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:4173/vagas/",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `rm -rf /tmp/vagas-site && mkdir -p /tmp/vagas-site && cp -a ${raiz}/target/roq /tmp/vagas-site/vagas && python3 -m http.server 4173 --bind 127.0.0.1 --directory /tmp/vagas-site`,
    url: "http://127.0.0.1:4173/vagas/",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
