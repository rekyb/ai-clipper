import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { VideoDocument } from '@/features/import/types';
import { useUploadVideo } from './useUploadVideo';
import { mockJsonFetch, withFreshSwr } from './test-utils';

const sampleDoc: VideoDocument = {
  id: '1',
  filename: 'sample.mp4',
  title: 'sample',
  source: 'upload',
  storagePath: '/x',
  fileSizeBytes: 100,
  status: 'imported',
  createdAt: '2026-05-17T00:00:00Z',
  updatedAt: '2026-05-17T00:00:00Z',
};

afterEach(() => vi.unstubAllGlobals());

describe('useUploadVideo', () => {
  it('returns the imported VideoDocument on success', async () => {
    mockJsonFetch({ data: sampleDoc, error: null }, true, 201);
    const { result } = renderHook(() => useUploadVideo(), { wrapper: withFreshSwr });
    const file = new File(['x'], 'sample.mp4', { type: 'video/mp4' });
    let returned: VideoDocument | null = null;
    await act(async () => {
      returned = await result.current.upload(file);
    });
    expect(returned).toEqual(sampleDoc);
    expect(result.current.error).toBeNull();
  });

  it('captures ApiError on rejection', async () => {
    mockJsonFetch(
      { data: null, error: { code: 'FILE_TOO_LARGE', message: 'too big' } },
      false,
      413,
    );
    const { result } = renderHook(() => useUploadVideo(), { wrapper: withFreshSwr });
    const file = new File(['x'], 'huge.mp4', { type: 'video/mp4' });
    let returned: VideoDocument | null = null;
    await act(async () => {
      returned = await result.current.upload(file);
    });
    expect(returned).toBeNull();
    expect(result.current.error?.code).toBe('FILE_TOO_LARGE');
  });

  it('toggles isUploading around the call', async () => {
    let resolveFetch!: (value: Response) => void;
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveFetch = resolve;
          }),
      ),
    );
    const { result } = renderHook(() => useUploadVideo(), { wrapper: withFreshSwr });
    const file = new File(['x'], 'sample.mp4', { type: 'video/mp4' });

    let inflight: Promise<VideoDocument | null>;
    act(() => {
      inflight = result.current.upload(file);
    });
    await Promise.resolve();
    expect(result.current.isUploading).toBe(true);

    await act(async () => {
      resolveFetch({
        ok: true,
        status: 201,
        json: () => Promise.resolve({ data: sampleDoc, error: null }),
      } as Response);
      await inflight;
    });
    expect(result.current.isUploading).toBe(false);
  });

  it('reset clears the error', async () => {
    mockJsonFetch(
      { data: null, error: { code: 'X', message: 'bad' } },
      false,
      500,
    );
    const { result } = renderHook(() => useUploadVideo(), { wrapper: withFreshSwr });
    const file = new File(['x'], 'sample.mp4', { type: 'video/mp4' });
    await act(async () => {
      await result.current.upload(file);
    });
    expect(result.current.error).not.toBeNull();
    act(() => result.current.reset());
    expect(result.current.error).toBeNull();
  });
});
