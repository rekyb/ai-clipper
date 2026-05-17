import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { VideoDocument } from '@/features/import/types';
import { useDeleteVideo } from './useDeleteVideo';
import { useVideos } from './useVideos';
import { withFreshSwr } from './test-utils';

const videoA: VideoDocument = {
  id: 'a',
  filename: 'a.mp4',
  title: 'a',
  source: 'upload',
  storagePath: '/x',
  fileSizeBytes: 1,
  status: 'imported',
  createdAt: '2026-05-17T00:00:00Z',
  updatedAt: '2026-05-17T00:00:00Z',
};

const videoB: VideoDocument = { ...videoA, id: 'b', filename: 'b.mp4', title: 'b' };

afterEach(() => vi.unstubAllGlobals());

describe('useDeleteVideo', () => {
  it('calls DELETE and clears the row from the cache', async () => {
    const responses = [
      { data: { videos: [videoA, videoB] }, error: null },
      { data: { id: 'a', deleted: true }, error: null },
      { data: { videos: [videoB] }, error: null },
    ];
    let call = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(() => {
        const body = responses[Math.min(call++, responses.length - 1)];
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(body),
        } as Response);
      }),
    );

    const { result } = renderHook(
      () => ({ list: useVideos(), del: useDeleteVideo() }),
      { wrapper: withFreshSwr },
    );

    await waitFor(() => expect(result.current.list.videos.length).toBe(2));

    let ok = false;
    await act(async () => {
      ok = await result.current.del.remove('a');
    });
    expect(ok).toBe(true);
    await waitFor(() => expect(result.current.list.videos.find((v) => v.id === 'a')).toBeUndefined());
  });

  it('surfaces ApiError and leaves the list intact on failure', async () => {
    const responses: Array<{ ok: boolean; status: number; body: unknown }> = [
      { ok: true, status: 200, body: { data: { videos: [videoA, videoB] }, error: null } },
      {
        ok: false,
        status: 500,
        body: { data: null, error: { code: 'STORAGE_ERROR', message: 'oops' } },
      },
    ];
    let call = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(() => {
        const r = responses[Math.min(call++, responses.length - 1)];
        return Promise.resolve({
          ok: r.ok,
          status: r.status,
          json: () => Promise.resolve(r.body),
        } as Response);
      }),
    );

    const { result } = renderHook(
      () => ({ list: useVideos(), del: useDeleteVideo() }),
      { wrapper: withFreshSwr },
    );

    await waitFor(() => expect(result.current.list.videos.length).toBe(2));

    await act(async () => {
      await result.current.del.remove('a');
    });

    expect(result.current.del.error?.code).toBe('STORAGE_ERROR');
    await waitFor(() => expect(result.current.list.videos.length).toBe(2));
  });
});
