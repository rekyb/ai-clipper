import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { withThemeAndSwr } from '@/features/import/hooks/test-utils';
import type { VideoDocument } from '@/features/import/types';
import { VideoCard } from './index';

class FakeSocket {
  static instances: FakeSocket[] = [];
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeSocket.instances.push(this);
  }

  send(): void {}
  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }
}

beforeEach(() => {
  FakeSocket.instances = [];
  vi.stubGlobal('WebSocket', FakeSocket);
});

afterEach(() => vi.unstubAllGlobals());

const baseVideo: VideoDocument = {
  id: 'v1',
  filename: 'sample.mp4',
  title: 'My Podcast',
  source: 'upload',
  storagePath: '/path/sample.mp4',
  fileSizeBytes: 524_288_000,
  durationSec: 1834.5,
  thumbnailPath: '/path/thumbs/v1.jpg',
  status: 'imported',
  createdAt: '2026-05-17T00:00:00Z',
  updatedAt: '2026-05-17T00:00:00Z',
};

describe('VideoCard', () => {
  it('renders title, file size, and duration', () => {
    render(<VideoCard video={baseVideo} onDelete={vi.fn()} />, { wrapper: withThemeAndSwr });
    expect(screen.getByText('My Podcast')).toBeInTheDocument();
    expect(screen.getByText('500 MB')).toBeInTheDocument();
    expect(screen.getByText('30:34')).toBeInTheDocument();
  });

  it('shows the Imported status chip', () => {
    render(<VideoCard video={baseVideo} onDelete={vi.fn()} />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('status-chip-imported')).toBeInTheDocument();
  });

  it('fires onDelete when the trash icon is clicked', async () => {
    const onDelete = vi.fn();
    render(<VideoCard video={baseVideo} onDelete={onDelete} />, { wrapper: withThemeAndSwr });
    await userEvent.click(screen.getByLabelText('delete My Podcast'));
    expect(onDelete).toHaveBeenCalledWith(baseVideo);
  });

  it('renders the failed status chip and Retry button but hides the raw error text', () => {
    const failed: VideoDocument = {
      ...baseVideo,
      status: 'failed',
      errorCode: 'AUDIO_DECODE_FAILED',
      errorMessage: 'bad audio',
    };
    render(<VideoCard video={failed} onDelete={vi.fn()} />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('status-chip-failed')).toBeInTheDocument();
    expect(screen.getByTestId('retry-v1')).toBeInTheDocument();
    expect(screen.queryByText('bad audio')).not.toBeInTheDocument();
  });

  it('falls back to a blank placeholder when no thumbnail', () => {
    const noThumb = { ...baseVideo, thumbnailPath: null };
    render(<VideoCard video={noThumb} onDelete={vi.fn()} />, { wrapper: withThemeAndSwr });
    expect(screen.queryByAltText('My Podcast')).not.toBeInTheDocument();
  });

  it('renders the queue-position pill (not the status chip) when queued', () => {
    const queued: VideoDocument = { ...baseVideo, status: 'queued' };
    render(<VideoCard video={queued} onDelete={vi.fn()} />, { wrapper: withThemeAndSwr });
    expect(screen.queryByTestId('status-chip-queued')).toBeNull();
    // Opens a WS so progress hook is active.
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it('renders the progress overlay (not the status chip) when transcribing', () => {
    const transcribing: VideoDocument = {
      ...baseVideo,
      status: 'transcribing',
      lastProgressPercent: 47,
    };
    render(<VideoCard video={transcribing} onDelete={vi.fn()} />, { wrapper: withThemeAndSwr });
    expect(screen.queryByTestId('status-chip-transcribing')).toBeNull();
    expect(screen.getByTestId('progress-percent').textContent).toBe('47%');
  });

  it('shows the Ready status chip when status=ready', () => {
    const ready: VideoDocument = { ...baseVideo, status: 'ready' };
    render(<VideoCard video={ready} onDelete={vi.fn()} />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('status-chip-ready')).toBeInTheDocument();
  });

  it('does not open a websocket for non-active states', () => {
    render(<VideoCard video={baseVideo} onDelete={vi.fn()} />, { wrapper: withThemeAndSwr });
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it('renders the resumption hint when restartedAt is recent', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-17T10:00:00Z'));
    const queuedAfterRestart: VideoDocument = {
      ...baseVideo,
      status: 'queued',
      restartedAt: '2026-05-17T09:59:50Z',
    };
    render(<VideoCard video={queuedAfterRestart} onDelete={vi.fn()} />, {
      wrapper: withThemeAndSwr,
    });
    expect(screen.getByTestId('resumption-hint')).toBeInTheDocument();
    vi.useRealTimers();
  });

  it('does NOT render the resumption hint when restartedAt is stale', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-17T10:00:00Z'));
    const queuedStale: VideoDocument = {
      ...baseVideo,
      status: 'queued',
      restartedAt: '2026-05-17T09:00:00Z',
    };
    render(<VideoCard video={queuedStale} onDelete={vi.fn()} />, {
      wrapper: withThemeAndSwr,
    });
    expect(screen.queryByTestId('resumption-hint')).toBeNull();
    vi.useRealTimers();
  });
});
