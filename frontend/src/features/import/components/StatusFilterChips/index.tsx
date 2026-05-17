'use client';

import { Chip, Stack } from '@mui/material';

import type { VideoStatus } from '@/features/import/types';

type Filter = VideoStatus | 'all';

const OPTIONS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'uploading', label: 'Uploading' },
  { value: 'imported', label: 'Imported' },
  { value: 'failed', label: 'Failed' },
];

export function StatusFilterChips({
  value,
  onChange,
}: Readonly<{
  value: Filter;
  onChange: (next: Filter) => void;
}>) {
  return (
    <Stack direction="row" spacing={1} role="radiogroup" aria-label="Filter videos by status">
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

export type { Filter as StatusFilter };
