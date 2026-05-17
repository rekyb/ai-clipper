'use client';

import { Chip, Stack } from '@mui/material';

import type { VideoStatus } from '@/features/import/types';

export type StatusFilter = 'all' | 'importing' | VideoStatus;

const OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'importing', label: 'Importing' },
  { value: 'queued', label: 'Queued' },
  { value: 'transcribing', label: 'Transcribing' },
  { value: 'ready', label: 'Ready' },
  { value: 'failed', label: 'Failed' },
];

export function StatusFilterChips({
  value,
  onChange,
}: Readonly<{
  value: StatusFilter;
  onChange: (next: StatusFilter) => void;
}>) {
  return (
    <Stack
      direction="row"
      spacing={1}
      role="radiogroup"
      aria-label="Filter videos by status"
      sx={{ flexWrap: 'wrap', rowGap: 1 }}
    >
      {OPTIONS.map((opt) => {
        const selected = value === opt.value;
        return (
          <Chip
            key={opt.value}
            label={opt.label}
            clickable
            color={selected ? 'primary' : 'default'}
            variant={selected ? 'filled' : 'outlined'}
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(opt.value)}
            sx={{
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              fontWeight: 600,
              fontSize: 12,
              height: 28,
              borderRadius: 999,
            }}
          />
        );
      })}
    </Stack>
  );
}
