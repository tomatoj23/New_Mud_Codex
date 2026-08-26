import { defineConfig, devices } from "@playwright/test";

const python =
  process.env.PLAYWRIGHT_PYTHON ??
  (process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    channel: process.env.PLAYWRIGHT_CHANNEL,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: "mobile-modern-high-dpi",
      use: {
        ...devices["Galaxy S9+"],
        viewport: { width: 412, height: 915 },
        deviceScaleFactor: 3,
      },
    },
    {
      name: "mobile-ultrawide-landscape",
      use: {
        ...devices["Galaxy S9+"],
        viewport: { width: 915, height: 412 },
        deviceScaleFactor: 3,
      },
    },
  ],
  webServer: [
    {
      command:
        `${python} manage.py runserver 127.0.0.1:8000 --noreload`,
      cwd: "..",
      url: "http://127.0.0.1:8000/api/v1/health/live",
      reuseExistingServer: !process.env.CI,
      env: {
        ...process.env,
        DJANGO_SETTINGS_MODULE: "new_mud.settings.development",
      },
      timeout: 120_000,
    },
    {
      command:
        "node node_modules/@dcloudio/vite-plugin-uni/bin/uni.js -p h5 --host localhost --port 5173",
      cwd: ".",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
