'use client';

import { Box, Typography } from '@mui/material';
import { RefreshCwIcon } from 'lucide-react';

const HINT_VISIBLE_MS = 30_000;

export function isResumptionRecent(restartedAt: string | null | undefined): boolean {
  if (!restartedAt) return false;
  const ts = Date.parse(restartedAt);
  if (Number.isNaN(ts)) return false;
  return Date.now() - ts < HINT_VISIBLE_MS;
}

export function ResumptionHint() {
  return (
    <Box
      data-testid="resumption-hint"
      role="status"
      aria-live="polite"
      sx={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        alignItems: 'center',
        gap: 0.75,
        px: 1.5,
        py: 0.75,
        bgcolor: 'rgba(0, 0, 0, 0.55)',
        color: 'rgba(255,255,255,0.85)',
        backdropFilter: 'blur(6px)',
      }}
    >
      <RefreshCwIcon size={14} strokeWidth={1.75} />
      <Typography variant="body2" sx={{ color: 'inherit', lineHeight: 1.2 }}>
        Picking up where we left off…
      </Typography>
    </Box>
  );
}
