import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { mockJsonFetch, withThemeAndSwr } from '@/features/import/hooks/test-utils';
import { UrlImportForm } from './index';

afterEach(() => vi.unstubAllGlobals());

describe('UrlImportForm', () => {
  it('rejects non-YouTube URLs client-side without calling fetch', async () => {
    const spy = vi.fn(() => Promise.resolve(new Response()));
    vi.stubGlobal('fetch', spy);

    render(<UrlImportForm />, { wrapper: withThemeAndSwr });
    await userEvent.type(screen.getByLabelText('YouTube URL'), 'https://vimeo.com/123');
    await userEvent.click(screen.getByRole('button', { name: /Import from URL/ }));

    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByText(/Only YouTube URLs are supported/)).toBeInTheDocument();
  });

  it('submits a youtu.be URL via POST', async () => {
    const spy = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 202,
        json: () =>
          Promise.resolve({
            data: {
              id: 'p1',
              filename: '',
              title: 'https://youtu.be/x',
              source: 'youtube',
              sourceUrl: 'https://youtu.be/x',
              storagePath: '',
              fileSizeBytes: 0,
              status: 'uploading',
              createdAt: '2026-05-17T00:00:00Z',
              updatedAt: '2026-05-17T00:00:00Z',
            },
            error: null,
          }),
      } as Response),
    );
    vi.stubGlobal('fetch', spy);

    render(<UrlImportForm />, { wrapper: withThemeAndSwr });
    await userEvent.type(screen.getByLabelText('YouTube URL'), 'https://youtu.be/x');
    await userEvent.click(screen.getByRole('button', { name: /Import from URL/ }));

    expect(spy).toHaveBeenCalled();
    expect(spy.mock.calls[0][1]?.method).toBe('POST');
  });

  it('surfaces backend errors', async () => {
    mockJsonFetch(
      { data: null, error: { code: 'UNSUPPORTED_HOST', message: 'youtube only' } },
      false,
      400,
    );

    render(<UrlImportForm />, { wrapper: withThemeAndSwr });
    await userEvent.type(screen.getByLabelText('YouTube URL'), 'https://youtube.com/watch?v=x');
    await userEvent.click(screen.getByRole('button', { name: /Import from URL/ }));

    expect(await screen.findByText('youtube only')).toBeInTheDocument();
  });
});
