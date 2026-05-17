'use client';

import { Box, LinearProgress, Stack, Typography } from '@mui/material';

import type { TranscriptionState } from '@/lib/useTranscriptionProgress';

const scrim = 'rgba(0, 0, 0, 0.4)';

export function formatEta(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

export function ProgressOverlay({ progress }: Readonly<{ progress: TranscriptionState }>) {
  const percent = Math.max(0, Math.min(100, progress.percent));
  return (
    <Box
      role="presentation"
      sx={{
        position: 'absolute',
        inset: 0,
        backgroundColor: scrim,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      <Stack alignItems="center" spacing={0.5} sx={{ pb: 1 }}>
        <Typography
          variant="overline"
          sx={{ color: 'common.white', letterSpacing: '0.05em' }}
        >
          Transcribing
        </Typography>
        <Typography
          component="span"
          sx={{
            fontFamily: 'var(--font-jetbrains-mono), ui-monospace, monospace',
            fontSize: 24,
            fontWeight: 600,
            color: 'common.white',
            lineHeight: 1,
          }}
          data-testid="progress-percent"
        >
          {percent}%
        </Typography>
        {progress.etaSec !== null && progress.etaSec > 0 && (
          <Typography
            variant="body2"
            sx={{ color: 'rgba(255,255,255,0.75)' }}
            data-testid="progress-eta"
          >
            ~{formatEta(progress.etaSec)} left
          </Typography>
        )}
      </Stack>
      <LinearProgress
        variant="determinate"
        value={percent}
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Transcribing, ${percent}% complete`}
        sx={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: 4,
          backgroundColor: 'surfaceContainerHigh',
          '& .MuiLinearProgress-bar': {
            backgroundColor: 'primary.main',
            transition: 'transform 600ms cubic-bezier(0.4, 0, 0.2, 1)',
          },
          '@media (prefers-reduced-motion: reduce)': {
            '& .MuiLinearProgress-bar': { transition: 'none' },
          },
        }}
      />
    </Box>
  );
}
