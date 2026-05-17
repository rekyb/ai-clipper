import { defineConfig } from '@playwright/test';

const BACKEND_PORT = process.env.E2E_BACKEND_PORT ?? '8001';
const FRONTEND_PORT = process.env.E2E_FRONTEND_PORT ?? '3001';
const FRONTEND_URL = `http://localhost:${FRONTEND_PORT}`;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: FRONTEND_URL,
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `uv --directory ../backend run uvicorn app.main:app --port ${BACKEND_PORT}`,
      url: `${BACKEND_URL}/health`,
      timeout: 30_000,
      reuseExistingServer: !process.env.CI,
      env: {
        MONGODB_DB: 'ai_clipper_e2e',
        MEDIA_DIR: '../backend/.e2e-media',
      },
    },
    {
      command: `next dev --port ${FRONTEND_PORT}`,
      url: FRONTEND_URL,
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
      env: {
        NEXT_PUBLIC_API_URL: BACKEND_URL,
      },
    },
  ],
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
