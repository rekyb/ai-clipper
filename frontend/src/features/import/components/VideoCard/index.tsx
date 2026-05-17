'use client';

import { Box, IconButton, Stack, Typography } from '@mui/material';
import { Trash2Icon } from 'lucide-react';

import { StatusChip } from '@/features/import/components/StatusChip';
import { formatBytes, formatDuration } from '@/features/import/lib/format';
import { cardSurface } from '@/features/import/lib/surfaces';
import type { VideoDocument } from '@/features/import/types';
import { API_URL } from '@/lib/env';

export function VideoCard({
  video,
  onDelete,
}: {
  video: VideoDocument;
  onDelete: (video: VideoDocument) => void;
}) {
  const thumbUrl = video.thumbnailPath ? buildThumbnailUrl(video.thumbnailPath) : null;
  const created = new Date(video.createdAt).toLocaleDateString();

  return (
    <Box
      sx={{ ...cardSurface, p: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
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
        <Box sx={{ position: 'absolute', top: 8, left: 8 }}>
          <StatusChip status={video.status} />
        </Box>
        {video.durationSec != null && (
          <Box
            sx={{
              position: 'absolute',
              bottom: 8,
              right: 8,
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
      </Box>

      <Stack spacing={0.5} sx={{ p: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
          <Typography
            variant="h3"
            sx={{
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={video.title}
          >
            {video.title || video.filename || 'Untitled'}
          </Typography>
          <IconButton
            aria-label={`delete ${video.title}`}
            size="small"
            onClick={() => onDelete(video)}
          >
            <Trash2Icon size={18} strokeWidth={1.5} />
          </IconButton>
        </Stack>
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
        {video.status === 'failed' && video.errorMessage && (
          <Typography variant="body2" color="error.main">
            {video.errorMessage}
          </Typography>
        )}
      </Stack>
    </Box>
  );
}

function buildThumbnailUrl(thumbnailPath: string): string {
  const filename = thumbnailPath.split(/[\\/]/).pop() ?? '';
  return `${API_URL}/media/thumbnails/${filename}`;
}
