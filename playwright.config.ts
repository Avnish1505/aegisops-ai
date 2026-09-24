import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end tests against the real API (scripts/e2e_server.sh: SQLite, the Lucknow exercise
 * snapshot, demo triage reports; no model, no OSRM) and the production build of the console.
 * One worker: the tests share one database and run in order.
 */
export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:4173',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: 'sh scripts/e2e_server.sh',
      url: 'http://localhost:8010/health/ready',
      reuseExistingServer: false,
      stdout: 'ignore',
      timeout: 120_000,
    },
    {
      command: 'npm run build && npx vite preview --port 4173 --strictPort',
      url: 'http://localhost:4173',
      reuseExistingServer: false,
      timeout: 180_000,
      env: { VITE_API_BASE_URL: 'http://localhost:8010', VITE_AUTH_MODE: 'dev', VITE_MAP_STYLE: 'blank' },
    },
  ],
})
