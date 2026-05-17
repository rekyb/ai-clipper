'use client';

import { Box, Typography } from '@mui/material';

function ordinalLabel(position: number): string {
  if (position === 1) return 'NEXT UP';
  const lastTwo = position % 100;
  const last = position % 10;
  const suffix =
    lastTwo >= 11 && lastTwo <= 13
      ? 'TH'
      : last === 1
        ? 'ST'
        : last === 2
          ? 'ND'
          : last === 3
            ? 'RD'
            : 'TH';
  return `${position}${suffix} IN QUEUE`;
}

export function QueuePositionPill({
  position,
}: Readonly<{ position: number | null }>) {
  if (position === null || position < 1) return null;
  const isNext = position === 1;
  return (
    <Box
      data-testid="queue-position-pill"
      sx={{
        position: 'absolute',
        top: 8,
        right: 8,
        px: 1,
        py: 0.25,
        borderRadius: 999,
        bgcolor: isNext ? 'tertiaryContainer' : 'surfaceContainerHighest',
        color: isNext ? 'tertiary.main' : 'text.secondary',
        animation: isNext ? 'pulse 2s ease-in-out infinite' : 'none',
        '@keyframes pulse': {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.6 },
        },
        '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
      }}
    >
      <Typography
        variant="overline"
        sx={{ letterSpacing: '0.05em', lineHeight: 1.4 }}
      >
        {ordinalLabel(position)}
      </Typography>
    </Box>
  );
}
