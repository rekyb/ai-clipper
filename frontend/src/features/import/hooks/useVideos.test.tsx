import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { VideoDocument } from '@/features/import/types';
import { useVideos } from './useVideos';
import { mockJsonFetch, withFreshSwr } from './test-utils';

const imported: VideoDocument = {
  id: '1',
  filename: 'a.mp4',
  title: 'A',
  source: 'upload',
  storagePath: '/x',
  fileSizeBytes: 1,
  status: 'imported',
  createdAt: '2026-05-17T00:00:00Z',
  updatedAt: '2026-05-17T00:00:00Z',
};

const uploading: VideoDocument = { ...imported, id: '2', status: 'uploading' };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useVideos', () => {
  it('returns videos from the API envelope', async () => {
    mockJsonFetch({ data: { videos: [imported] }, error: null });
    const { result } = renderHook(() => useVideos(), { wrapper: withFreshSwr });
    await waitFor(() => expect(result.current.videos.length).toBe(1));
    expect(result.current.videos[0].filename).toBe('a.mp4');
  });

  it('returns an empty array while loading', () => {
    mockJsonFetch({ data: { videos: [] }, error: null });
    const { result } = renderHook(() => useVideos(), { wrapper: withFreshSwr });
    expect(result.current.videos).toEqual([]);
  });

  it('passes the status query param to the API when given', async () => {
    const spy = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ data: { videos: [] }, error: null }),
      } as Response),
    );
    vi.stubGlobal('fetch', spy);

    renderHook(() => useVideos('failed'), { wrapper: withFreshSwr });
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0]).toMatch(/\?status=failed$/);
  });

  it('surfaces API errors via the error field', async () => {
    mockJsonFetch(
      { data: null, error: { code: 'BOOM', message: 'kaboom' } },
      false,
      500,
    );
    const { result } = renderHook(() => useVideos(), { wrapper: withFreshSwr });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.error?.code).toBe('BOOM');
  });

  it('exposes mutate for cache invalidation', async () => {
    mockJsonFetch({ data: { videos: [uploading] }, error: null });
    const { result } = renderHook(() => useVideos(), { wrapper: withFreshSwr });
    await waitFor(() => expect(result.current.videos.length).toBe(1));
    await act(async () => {
      await result.current.mutate();
    });
    expect(result.current.videos.length).toBe(1);
  });
});
