'use client';

import { Box, IconButton, Stack, Typography } from '@mui/material';
import { Trash2Icon } from 'lucide-react';

import { ProgressOverlay } from '@/features/import/components/VideoCard/ProgressOverlay';
import { QueuePositionPill } from '@/features/import/components/VideoCard/QueuePositionPill';
import {
  ResumptionHint,
  isResumptionRecent,
} from '@/features/import/components/VideoCard/ResumptionHint';
import { RetryButton } from '@/features/import/components/VideoCard/RetryButton';
import { StatusChip } from '@/features/import/components/StatusChip';
import { formatBytes, formatDuration } from '@/features/import/lib/format';
import { cardSurface } from '@/lib/surfaces';
import type { VideoDocument } from '@/features/import/types';
import { API_URL } from '@/lib/env';
import { useTranscriptionProgress } from '@/lib/useTranscriptionProgress';

const ACTIVE_STATES = new Set<VideoDocument['status']>(['queued', 'transcribing']);

export function VideoCard({
  video,
  onDelete,
}: Readonly<{
  video: VideoDocument;
  onDelete: (video: VideoDocument) => void;
}>) {
  const thumbUrl = video.thumbnailPath ? buildThumbnailUrl(video.thumbnailPath) : null;
  const created = new Date(video.createdAt).toLocaleDateString();
  const isActive = ACTIVE_STATES.has(video.status);
  const progress = useTranscriptionProgress(video.id, { enabled: isActive });

  // Prefer the live progress percent (always 0..100) over the stale DB value.
  const effectivePercent =
    video.status === 'transcribing'
      ? Math.max(progress.percent, video.lastProgressPercent ?? 0)
      : 0;
  const effectiveQueuePosition =
    video.status === 'queued' ? progress.queuePosition : null;
  const showResumptionHint = isResumptionRecent(video.restartedAt);
  const showStatusChip =
    video.status !== 'transcribing' && video.status !== 'queued';

  return (
    <Box
      sx={{
        ...cardSurface,
        position: 'relative',
        p: 0,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Box
        sx={{
          position: 'relative',
          aspectRatio: '16 / 9',
          bgcolor: 'background.default',
        }}
      >
        {thumbUrl ? (
          <Box
            component="img"
            src={thumbUrl}
            alt={video.title}
            sx={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
          />
        ) : (
          <Box
            aria-hidden
            sx={{ width: '100%', height: '100%', bgcolor: 'background.default' }}
          />
        )}

        {showStatusChip && (
          <Box sx={{ position: 'absolute', top: 8, left: 8 }}>
            <StatusChip status={video.status} />
          </Box>
        )}

        {video.status === 'transcribing' && (
          <ProgressOverlay
            progress={{
              ...progress,
              percent: effectivePercent,
            }}
          />
        )}

        {video.status === 'queued' && (
          <QueuePositionPill position={effectiveQueuePosition} />
        )}

        {video.durationSec != null && (
          <Box
            sx={{
              position: 'absolute',
              // Move duration pill to bottom-left when queue-position pill takes top-right.
              bottom: 8,
              right: video.status === 'queued' ? 'auto' : 8,
              left: video.status === 'queued' ? 8 : 'auto',
              px: 1,
              py: 0.25,
              bgcolor: 'rgba(0,0,0,0.7)',
              color: 'common.white',
              borderRadius: 999,
              fontFamily: 'var(--font-jetbrains-mono), ui-monospace, monospace',
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            {formatDuration(video.durationSec)}
          </Box>
        )}

        {showResumptionHint && <ResumptionHint />}
      </Box>

      <Stack spacing={0.5} sx={{ p: 2, pr: video.status === 'failed' ? 2 : 7 }}>
        <Typography
          variant="h3"
          sx={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={video.title}
        >
          {video.title || video.filename || 'Untitled'}
        </Typography>
        <Typography
          component="span"
          sx={{
            fontFamily: 'var(--font-jetbrains-mono), ui-monospace, monospace',
            fontSize: 13,
            color: 'text.secondary',
          }}
        >
          {formatBytes(video.fileSizeBytes)}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {created}
        </Typography>
        {video.status === 'failed' && (
          <Stack direction="row" spacing={1} sx={{ pt: 1 }}>
            <RetryButton videoId={video.id} />
          </Stack>
        )}
      </Stack>

      <IconButton
        aria-label={`delete ${video.title}`}
        onClick={() => onDelete(video)}
        sx={{
          position: 'absolute',
          bottom: 12,
          right: 12,
          width: 36,
          height: 36,
          bgcolor: 'transparent',
          color: 'error.main',
          border: '1px solid',
          borderColor: 'error.main',
          '&:hover': { bgcolor: 'rgba(147, 0, 10, 0.12)', borderColor: 'error.main' },
          '&:focus-visible': { outline: 'none', boxShadow: '0 0 0 3px rgba(147, 0, 10, 0.35)' },
        }}
      >
        <Trash2Icon size={18} strokeWidth={1.75} />
      </IconButton>
    </Box>
  );
}

function buildThumbnailUrl(thumbnailPath: string): string {
  const filename = thumbnailPath.split(/[\\/]/).pop() ?? '';
  return `${API_URL}/media/thumbnails/${filename}`;
}
