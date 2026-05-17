import { execSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

import { expect, test } from '@playwright/test';

const BACKEND_URL = `http://localhost:${process.env.E2E_BACKEND_PORT ?? '8001'}`;

let fixturePath: string;

test.beforeAll(() => {
  const dir = join(tmpdir(), 'ai-clipper-e2e');
  mkdirSync(dir, { recursive: true });
  fixturePath = join(dir, 'sample.mp4');
  execSync(
    [
      'ffmpeg',
      '-loglevel',
      'error',
      '-y',
      '-f',
      'lavfi',
      '-i',
      'color=c=blue:size=320x240:rate=24',
      '-f',
      'lavfi',
      '-i',
      'anullsrc=channel_layout=stereo:sample_rate=48000',
      '-t',
      '5',
      '-c:v',
      'libx264',
      '-pix_fmt',
      'yuv420p',
      '-c:a',
      'aac',
      fixturePath,
    ].join(' '),
    { stdio: 'inherit' },
  );
});

test.beforeEach(async ({ request }) => {
  const res = await request.get(`${BACKEND_URL}/api/videos`);
  const body = (await res.json()) as { data: { videos: { id: string }[] } };
  for (const v of body.data.videos) {
    await request.delete(`${BACKEND_URL}/api/videos/${v.id}`);
  }
});

// The "real Whisper" verification is a manual checkpoint — this E2E covers the
// surfaces around it (auto-pickup, failure UX, retry, filter chips) without
// requiring the model to be loaded.
test('upload triggers auto-pickup into queued or active state', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Library', level: 2 })).toBeVisible();

  await page.getByLabel('Pick a video file').setInputFiles(fixturePath);

  const card = page.locator('img[alt="sample"]').first();
  await expect(card).toBeVisible({ timeout: 30_000 });

  // Auto-pickup should put the card into a transcription-pipeline state.
  await expect(
    page.locator('[data-testid^="queue-position-pill"], [data-testid^="progress-percent"]').first(),
  ).toBeVisible({ timeout: 10_000 });
});

test('failure surfaces Retry button which re-queues the video', async ({ page, request }) => {
  await page.goto('/');
  await page.getByLabel('Pick a video file').setInputFiles(fixturePath);

  // Wait until the backend marks the video failed (likely because the Whisper
  // model isn't installed in this env). If Whisper IS installed and transcription
  // succeeds, this test is harmless — it just won't find a retry button.
  let videoId = '';
  for (let i = 0; i < 30; i++) {
    const res = await request.get(`${BACKEND_URL}/api/videos`);
    const body = (await res.json()) as {
      data: { videos: { id: string; status: string }[] };
    };
    const failed = body.data.videos.find((v) => v.status === 'failed');
    if (failed) {
      videoId = failed.id;
      break;
    }
    if (body.data.videos.some((v) => v.status === 'ready')) {
      test.skip(true, 'Whisper transcription succeeded; retry path not exercised');
      return;
    }
    await page.waitForTimeout(1000);
  }
  expect(videoId, 'video should reach failed status within 30s').not.toBe('');

  // Reload to ensure the failed state is rendered with the Retry button.
  await page.reload();
  const retry = page.getByTestId(`retry-${videoId}`);
  await expect(retry).toBeVisible({ timeout: 10_000 });
  await retry.click();

  // After retry, status flips back to queued; the queue-position pill (or progress overlay)
  // appears again. Either pill counts as success.
  await expect(
    page.locator('[data-testid^="queue-position-pill"], [data-testid^="progress-percent"]').first(),
  ).toBeVisible({ timeout: 10_000 });
});

test('Transcribing chip is selectable in the status filter', async ({ page }) => {
  await page.goto('/');
  const transcribingChip = page.getByRole('radio', { name: 'Transcribing' });
  await expect(transcribingChip).toBeVisible();
  await transcribingChip.click();
  await expect(transcribingChip).toHaveAttribute('aria-checked', 'true');
});
