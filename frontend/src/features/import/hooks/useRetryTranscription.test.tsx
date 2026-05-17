import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useRetryTranscription } from './useRetryTranscription';
import { useVideos } from './useVideos';
import { withFreshSwr } from './test-utils';
import type { VideoDocument } from '@/features/import/types';

const failedVideo: VideoDocument = {
  id: 'a',
  filename: 'a.mp4',
  title: 'a',
  source: 'upload',
  storagePath: '/x',
  fileSizeBytes: 1,
  status: 'failed',
  errorCode: 'AUDIO_DECODE_FAILED',
  errorMessage: 'bad audio',
  createdAt: '2026-05-17T00:00:00Z',
  updatedAt: '2026-05-17T00:00:00Z',
};

afterEach(() => vi.unstubAllGlobals());

describe('useRetryTranscription', () => {
  it('POSTs to the retry endpoint and revalidates the videos list', async () => {
    const responses = [
      { ok: true, status: 200, body: { data: { videos: [failedVideo] }, error: null } },
      { ok: true, status: 200, body: { data: { id: 'a', status: 'queued' }, error: null } },
      {
        ok: true,
        status: 200,
        body: { data: { videos: [{ ...failedVideo, status: 'queued' }] }, error: null },
      },
    ];
    const fetchMock = vi.fn(() => {
      const r = responses[Math.min(fetchMock.mock.calls.length - 1, responses.length - 1)];
      return Promise.resolve({
        ok: r.ok,
        status: r.status,
        statusText: 'OK',
        json: () => Promise.resolve(r.body),
      } as Response);
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(
      () => ({ list: useVideos(), retry: useRetryTranscription() }),
      { wrapper: withFreshSwr },
    );

    await waitFor(() => expect(result.current.list.videos[0]?.status).toBe('failed'));

    await act(async () => {
      await result.current.retry.retry('a');
    });

    const postCall = fetchMock.mock.calls.find((c) => (c[1] as RequestInit)?.method === 'POST');
    expect(postCall?.[0]).toContain('/api/videos/a/retry');
    await waitFor(() => expect(result.current.list.videos[0]?.status).toBe('queued'));
  });

  it('surfaces ApiError from the retry endpoint', async () => {
    const responses = [
      {
        ok: false,
        status: 409,
        body: { data: null, error: { code: 'INVALID_TRANSITION', message: 'no' } },
      },
    ];
    vi.stubGlobal(
      'fetch',
      vi.fn(() => {
        const r = responses[0];
        return Promise.resolve({
          ok: r.ok,
          status: r.status,
          statusText: 'Conflict',
          json: () => Promise.resolve(r.body),
        } as Response);
      }),
    );

    const { result } = renderHook(() => useRetryTranscription(), { wrapper: withFreshSwr });

    await act(async () => {
      await result.current.retry('a');
    });

    expect(result.current.error?.code).toBe('INVALID_TRANSITION');
  });

  it('tracks loading state during the request', async () => {
    let resolveFetch: (() => void) | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveFetch = () =>
              resolve({
                ok: true,
                status: 200,
                statusText: 'OK',
                json: () => Promise.resolve({ data: { id: 'a', status: 'queued' }, error: null }),
              } as Response);
          }),
      ),
    );

    const { result } = renderHook(() => useRetryTranscription(), { wrapper: withFreshSwr });

    let pending: Promise<void> | undefined;
    act(() => {
      pending = result.current.retry('a');
    });
    await waitFor(() => expect(result.current.isLoading).toBe(true));
    act(() => resolveFetch?.());
    await act(async () => {
      await pending;
    });
    expect(result.current.isLoading).toBe(false);
  });
});
