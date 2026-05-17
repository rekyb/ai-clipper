import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { withThemeAndSwr } from '@/features/import/hooks/test-utils';
import { RetryButton } from './';

afterEach(() => vi.unstubAllGlobals());

describe('RetryButton', () => {
  it('POSTs to the retry endpoint when clicked', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: () => Promise.resolve({ data: { id: 'vid-1', status: 'queued' }, error: null }),
      } as Response),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(<RetryButton videoId="vid-1" />, { wrapper: withThemeAndSwr });
    fireEvent.click(screen.getByTestId('retry-vid-1'));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toContain('/api/videos/vid-1/retry');
    expect((call[1] as RequestInit).method).toBe('POST');
  });

  it('is disabled while the request is in flight', async () => {
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
                json: () => Promise.resolve({ data: { id: 'vid-1', status: 'queued' }, error: null }),
              } as Response);
          }),
      ),
    );

    render(<RetryButton videoId="vid-1" />, { wrapper: withThemeAndSwr });
    const btn = screen.getByTestId('retry-vid-1');
    fireEvent.click(btn);

    await waitFor(() => expect(btn).toBeDisabled());
    resolveFetch?.();
    await waitFor(() => expect(btn).not.toBeDisabled());
  });
});
