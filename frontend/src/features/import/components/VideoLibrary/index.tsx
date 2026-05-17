'use client';

import { Alert, Box, Button, Skeleton, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import { DeleteConfirmDialog } from '@/features/import/components/DeleteConfirmDialog';
import { EmptyState } from '@/features/import/components/EmptyState';
import {
  StatusFilterChips,
  type StatusFilter,
} from '@/features/import/components/StatusFilterChips';
import { VideoCard } from '@/features/import/components/VideoCard';
import { useDeleteVideo } from '@/features/import/hooks/useDeleteVideo';
import { useVideos } from '@/features/import/hooks/useVideos';
import type { VideoDocument } from '@/features/import/types';

const GRID_SX = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
  gap: 2,
};

export function VideoLibrary() {
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [target, setTarget] = useState<VideoDocument | null>(null);
  const status = filter === 'all' ? undefined : filter;
  const { videos, isLoading, error, mutate } = useVideos(status);
  const { remove, isDeleting } = useDeleteVideo();

  const confirmDelete = async () => {
    if (!target) return;
    const ok = await remove(target.id);
    setTarget(null);
    if (ok) await mutate();
  };

  return (
    <Box>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={2}
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        justifyContent="space-between"
        sx={{ mb: 3 }}
      >
        <Typography variant="h2">Library</Typography>
        <StatusFilterChips value={filter} onChange={setFilter} />
      </Stack>

      {isLoading && (
        <Box sx={GRID_SX}>
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="rounded" height={240} />
          ))}
        </Box>
      )}

      {error && (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => { mutate(); }}>
              Retry
            </Button>
          }
        >
          Couldn&apos;t load your videos: {error.message}
        </Alert>
      )}

      {!isLoading && !error && videos.length === 0 && filter === 'all' && (
        <EmptyState
          title="Your library is empty"
          body="Drop a video above or paste a YouTube URL to get started."
        />
      )}

      {!isLoading && !error && videos.length === 0 && filter !== 'all' && (
        <Typography variant="body2" color="text.secondary">
          No videos with this status.
        </Typography>
      )}

      {!isLoading && videos.length > 0 && (
        <Box sx={GRID_SX}>
          {videos.map((video) => (
            <VideoCard key={video.id} video={video} onDelete={setTarget} />
          ))}
        </Box>
      )}

      <DeleteConfirmDialog
        open={target !== null}
        title={target?.title ?? ''}
        isDeleting={isDeleting}
        onCancel={() => setTarget(null)}
        onConfirm={confirmDelete}
      />
    </Box>
  );
}
