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

test('upload -> appears in library -> delete -> empty state', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Library', level: 2 })).toBeVisible();
  await expect(page.getByText('Your library is empty')).toBeVisible();

  await page.getByLabel('Pick a video file').setInputFiles(fixturePath);

  const card = page.locator('img[alt="sample"]').first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  // After Chunk 2B, auto-pickup flips imported → queued within ~2s, so accept either.
  await expect(
    page
      .getByText(/Queued|Transcribing|Imported|Ready|Failed/, { exact: true })
      .first(),
  ).toBeVisible({ timeout: 5_000 });

  await page.getByLabel('delete sample').click();
  await expect(page.getByRole('button', { name: 'Delete' })).toBeVisible();
  await page.getByRole('button', { name: 'Delete' }).click();

  await expect(card).toBeHidden({ timeout: 10_000 });
  await expect(page.getByText('Your library is empty')).toBeVisible();
});
