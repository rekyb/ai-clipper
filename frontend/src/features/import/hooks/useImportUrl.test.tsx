import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { VideoDocument } from '@/features/import/types';
import { useImportUrl } from './useImportUrl';
import { mockJsonFetch, withFreshSwr } from './test-utils';

const placeholder: VideoDocument = {
  id: '1',
  filename: '',
  title: 'https://youtu.be/x',
  source: 'youtube',
  sourceUrl: 'https://youtu.be/x',
  storagePath: '',
  fileSizeBytes: 0,
  status: 'uploading',
  createdAt: '2026-05-17T00:00:00Z',
  updatedAt: '2026-05-17T00:00:00Z',
};

afterEach(() => vi.unstubAllGlobals());

describe('useImportUrl', () => {
  it('posts the URL and returns the placeholder doc', async () => {
    const spy = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 202,
        json: () => Promise.resolve({ data: placeholder, error: null }),
      } as Response),
    );
    vi.stubGlobal('fetch', spy);
    const { result } = renderHook(() => useImportUrl(), { wrapper: withFreshSwr });
    let returned: VideoDocument | null = null;
    await act(async () => {
      returned = await result.current.importUrl('https://youtu.be/x');
    });
    expect(returned).toEqual(placeholder);
    const call = spy.mock.calls[0];
    expect(call[1]?.method).toBe('POST');
    expect(JSON.parse(call[1]?.body as string)).toEqual({ url: 'https://youtu.be/x' });
  });

  it('captures UNSUPPORTED_HOST on rejection', async () => {
    mockJsonFetch(
      { data: null, error: { code: 'UNSUPPORTED_HOST', message: 'youtube only' } },
      false,
      400,
    );
    const { result } = renderHook(() => useImportUrl(), { wrapper: withFreshSwr });
    await act(async () => {
      await result.current.importUrl('https://vimeo.com/1');
    });
    expect(result.current.error?.code).toBe('UNSUPPORTED_HOST');
  });
});
