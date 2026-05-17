import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { withThemeAndSwr } from '@/features/import/hooks/test-utils';
import type { VideoDocument } from '@/features/import/types';
import { VideoCard } from './index';

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

  it('renders the error message when status is failed', () => {
    const failed: VideoDocument = {
      ...baseVideo,
      status: 'failed',
      errorCode: 'VIDEO_PRIVATE',
      errorMessage: 'private video',
    };
    render(<VideoCard video={failed} onDelete={vi.fn()} />, { wrapper: withThemeAndSwr });
    expect(screen.getByText('private video')).toBeInTheDocument();
    expect(screen.getByTestId('status-chip-failed')).toBeInTheDocument();
  });

  it('falls back to a blank placeholder when no thumbnail', () => {
    const noThumb = { ...baseVideo, thumbnailPath: null };
    render(<VideoCard video={noThumb} onDelete={vi.fn()} />, { wrapper: withThemeAndSwr });
    expect(screen.queryByAltText('My Podcast')).not.toBeInTheDocument();
  });
});
